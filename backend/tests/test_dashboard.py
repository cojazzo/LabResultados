"""
Dashboard: conteo por persona, filtros de fecha y semáforo KDIGO.
Todos los datos son sintéticos y viven en un periodo propio (2031) para no mezclarse
con otros tests de la misma base.
"""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Lote, Paciente, Prueba, Resultado

PERIODO = {"desde": "2031-01-01", "hasta": "2031-12-31"}
FECHA = date(2031, 3, 10)

PRUEBAS = {
    "CRTS": ("Creatinina Sérica", "mg/dL"),
    "CRE01": ("Creatinina Urinaria", "mg/dL"),
    "ALBOR": ("Albúmina en Orina", "mg/L"),
    "ACR": ("Relación Albúmina/Creatinina", "mg/g"),
}


async def _prueba(db, codigo):
    existente = (await db.execute(select(Prueba).where(Prueba.codigo == codigo))).scalar_one_or_none()
    if existente:
        return existente
    nombre, unidad = PRUEBAS[codigo]
    p = Prueba(codigo=codigo, nombre=nombre, unidad=unidad, categoria="Función Renal")
    db.add(p)
    await db.flush()
    return p


async def _paciente(db, ident, nacimiento=date(1990, 1, 1), sexo="M"):
    p = Paciente(identificacion=ident, nombre="Sintético", apellido=ident, sexo=sexo, fecha_nacimiento=nacimiento)
    db.add(p)
    await db.flush()
    return p


@pytest_asyncio.fixture
async def datos(db_session):
    """
    A: 4 pruebas el mismo día, creatinina normal y ACR 10      -> G1/A1 (bajo)
    B: solo ACR 100 (tira, sin creatinina sérica)              -> Sin TFG / A2
    C: creatinina alta (TFG baja) + ACR 500                    -> G3b o peor / A3 (muy alto)
    D: resultado fuera del periodo filtrado                    -> no cuenta en 2031
    """
    db = db_session
    # La base de test dura toda la sesión: los datos se crean una sola vez.
    if (await db.execute(select(Paciente).where(Paciente.identificacion == "DASH-A"))).scalar_one_or_none():
        return
    pr = {c: await _prueba(db, c) for c in PRUEBAS}
    lote = Lote(nombre="lote-sintetico-dashboard")
    db.add(lote)
    await db.flush()

    def res(pac, codigo, valor, fecha=FECHA, interp="normal"):
        return Resultado(
            paciente_id=pac.id, prueba_id=pr[codigo].id, lote_id=lote.id,
            valor=Decimal(str(valor)), fecha_toma=fecha, interpretacion=interp,
        )

    a = await _paciente(db, "DASH-A")
    b = await _paciente(db, "DASH-B")
    c = await _paciente(db, "DASH-C")
    d = await _paciente(db, "DASH-D")

    db.add_all([
        res(a, "CRTS", 0.8), res(a, "CRE01", 100), res(a, "ALBOR", 10), res(a, "ACR", 10),
        res(b, "ACR", 100, interp="alto"),
        res(c, "CRTS", 2.5, interp="alto"), res(c, "ACR", 500, interp="critico_alto"),
        res(d, "ACR", 10, fecha=date(2030, 6, 1)),
    ])
    await db.commit()


@pytest.mark.asyncio
async def test_resumen_cuenta_personas_no_determinaciones(client, auth_headers, datos):
    r = await client.get("/api/dashboard/resumen", params=PERIODO, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_personas"] == 3          # A, B y C; D está fuera del periodo
    assert data["total_determinaciones"] == 7   # A tiene 4, B 1, C 2
    assert data["personas_con_alteraciones"] == 2  # B y C


@pytest.mark.asyncio
async def test_filtro_de_fechas_se_aplica(client, auth_headers, datos):
    r = await client.get(
        "/api/dashboard/resumen",
        params={"desde": "2030-01-01", "hasta": "2030-12-31"},
        headers=auth_headers,
    )
    assert r.json()["total_personas"] == 1      # solo D


@pytest.mark.asyncio
async def test_rango_invertido_es_error(client, auth_headers):
    r = await client.get(
        "/api/dashboard/resumen",
        params={"desde": "2031-12-31", "hasta": "2031-01-01"},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_tendencia_cuenta_una_vez_por_persona(client, auth_headers, datos):
    r = await client.get(
        "/api/dashboard/tendencia", params={**PERIODO, "periodo": "dia"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json() == [{"periodo": "2031-03-10", "cantidad": 3}]


@pytest.mark.asyncio
async def test_tendencia_vacia_no_inventa_datos(client, auth_headers):
    r = await client.get(
        "/api/dashboard/tendencia",
        params={"desde": "2099-01-01", "hasta": "2099-12-31"},
        headers=auth_headers,
    )
    assert r.json() == []


@pytest.mark.asyncio
async def test_semaforo_kdigo(client, auth_headers, datos):
    r = await client.get("/api/dashboard/riesgo-kdigo", params=PERIODO, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    celdas = {(c["g"], c["a"]): c for c in data["celdas"]}

    assert data["total_personas"] == 3
    assert data["sin_clasificar"] == 0
    assert celdas[("G1", "A1")]["cantidad"] == 1 and celdas[("G1", "A1")]["color"] == "green"
    assert celdas[("Sin TFG", "A2")]["cantidad"] == 1
    # C: creatinina 2.5 mg/dL en adulto joven -> TFG baja, albuminuria A3 -> riesgo muy alto
    assert celdas[("G3b", "A3")]["color"] == "red" or celdas[("G4", "A3")]["color"] == "red"
    assert sum(c["cantidad"] for c in data["celdas"]) == 3
    assert data["por_riesgo"]["bajo"] == 1
    assert data["por_riesgo"]["muy_alto"] == 1
    assert data["completas"] == 2


@pytest.mark.asyncio
async def test_top_pruebas_cuenta_personas(client, auth_headers, datos):
    r = await client.get("/api/dashboard/top-pruebas", params=PERIODO, headers=auth_headers)
    top = {t["codigo"]: t["cantidad"] for t in r.json()}
    assert top["ACR"] == 3   # A, B y C una vez cada una
    assert top["CRTS"] == 2  # A y C


@pytest_asyncio.fixture
async def persona_de_ayer(db_session):
    from datetime import timedelta
    db = db_session
    ayer = date.today() - timedelta(days=1)
    if (await db.execute(select(Paciente).where(Paciente.identificacion == "DASH-AYER"))).scalar_one_or_none():
        return ayer
    pr = {c: await _prueba(db, c) for c in PRUEBAS}
    lote = Lote(nombre="lote-sintetico-ayer")
    db.add(lote)
    await db.flush()
    p = await _paciente(db, "DASH-AYER")
    for cod, v in [("ACR", 12), ("CRE01", 90), ("ALBOR", 11)]:
        db.add(Resultado(paciente_id=p.id, prueba_id=pr[cod].id, lote_id=lote.id,
                         valor=Decimal(str(v)), fecha_toma=ayer, interpretacion="normal"))
    await db.commit()
    return ayer


@pytest.mark.asyncio
async def test_recientes_unifica_por_persona_el_dia_anterior(client, auth_headers, persona_de_ayer):
    r = await client.get("/api/dashboard/recientes", params={"limit": 100}, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["fecha"] == persona_de_ayer.isoformat()
    filas = [i for i in data["items"] if i["paciente"].startswith("Sintético DASH-AYER")]
    assert len(filas) == 1                                   # una fila por persona
    assert set(filas[0]["valores"]) == {"ACR", "CRE01", "ALBOR"}
    assert filas[0]["valores"]["ACR"]["valor"] == 12
