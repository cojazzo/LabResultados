"""
Pruebas de la integración con tamiz-escolar.
Todos los datos son ficticios (folios, CURP y nombres inventados).
"""
import csv
import io
import json
from datetime import date

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Campana, CampanaPaciente, Lote, Paciente, Prueba, Resultado, User
from app.services.excel_parser import process_horizontal_excel
from app.services.tamiz_sync import (
    fecha_toma_tamiz, normalizar_folio, resolver_folio, sincronizar_alumnos,
)
from app.services.uc1000_parser import process_uc1000_csv

CURP_A = "TEST010101HASAAA01"
CURP_B = "TEST020202MASBBB02"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool,
                                 connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        session.add(User(username="u", email="u@x.mx", hashed_password="x", nombre_completo="U"))
        await session.commit()
        yield session
    await engine.dispose()


def alumno(folio="S00000001", curp=CURP_A, **extra):
    base = {"folio": folio, "curp": curp, "nombres": "ANA", "primer_apellido": "PRUEBA",
            "segundo_apellido": "UNO", "fecha_nacimiento": "2011-03-05", "sexo": "H",
            "cct": "01DES0000X", "escuela": "SECUNDARIA DE PRUEBA", "turno": "MATUTINO",
            "grado": 3, "grupo": "A", "ronda": 1, "fecha_evaluacion": "2026-10-19"}
    base.update(extra)
    return base


def csv_tira(filas):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["UC-1000 DATA"] + [""] * 80)
    w.writerow(["Version", "Id"] + [""] * 79)
    for id_, fecha, cre, alb in filas:
        row = [""] * 81
        row[1], row[8], row[74], row[80] = id_, fecha, cre, alb
        w.writerow(row)
    return out.getvalue().encode("utf-8")


async def valores(db, paciente_id):
    res = await db.execute(select(Resultado, Prueba).join(Prueba, Prueba.id == Resultado.prueba_id)
                           .where(Resultado.paciente_id == paciente_id))
    return {(p.codigo, r.fecha_toma): (float(r.valor), r.fuente) for r, p in res.all() if r.valor is not None}


# ---------------------------------------------------------------------------

def test_normalizar_folio():
    assert normalizar_folio("S26136937") == "S26136937"
    assert normalizar_folio(" s26136937 ") == "S26136937"
    assert normalizar_folio("17S26136937") == "S26136937"      # con modificador del UC-1000
    assert normalizar_folio("1799921732") is None               # ID de petición del servicio externo
    assert normalizar_folio("99921732") is None
    assert normalizar_folio(None) is None
    assert normalizar_folio("S2613693") is None


@pytest.mark.asyncio
async def test_sincronizar_crea_inscribe_y_es_idempotente(db):
    r1 = await sincronizar_alumnos(db, [alumno()])
    assert r1["creados"] == 1 and r1["inscritos_nuevos"] == 1 and not r1["conflictos"]

    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == CURP_A and p.origen == "secundaria" and p.apellido == "PRUEBA"
    camp = (await db.execute(select(Campana))).scalar_one()
    assert camp.slug == "secundarias-2026-2027" and camp.tipo == "secundaria"
    cp = (await db.execute(select(CampanaPaciente))).scalar_one()
    ctx = json.loads(cp.datos_contextuales)
    assert ctx["cct"] == "01DES0000X" and ctx["fecha_evaluacion"] == "2026-10-19"

    r2 = await sincronizar_alumnos(db, [alumno()])
    assert r2["creados"] == 0 and r2["sin_cambios"] == 1 and r2["inscritos_nuevos"] == 0
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_alumno_sin_curp_usa_folio_y_despues_recibe_curp(db):
    await sincronizar_alumnos(db, [alumno(curp=None)])
    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == "TAMIZ-S00000001"

    r = await sincronizar_alumnos(db, [alumno(curp=CURP_A)])
    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == CURP_A and r["curp_asignada"] == 1
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_paciente_existente_por_curp_recibe_el_folio(db):
    db.add(Paciente(identificacion=CURP_A, nombre="ANA", apellido="PRUEBA", origen="servicio_externo"))
    await db.flush()
    r = await sincronizar_alumnos(db, [alumno()])
    assert r["creados"] == 0 and r["actualizados"] == 1
    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == CURP_A and p.origen == "secundaria"
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_misma_curp_en_dos_folios_es_conflicto(db):
    r = await sincronizar_alumnos(db, [alumno("S00000001", CURP_A), alumno("S00000002", CURP_A)])
    assert r["creados"] == 1 and len(r["conflictos"]) == 1
    assert await resolver_folio(db, "S00000002") is None


@pytest.mark.asyncio
async def test_sexo_se_convierte_de_tamiz_a_lab(db):
    """Tamiz usa la convención de la CURP (H = hombre, M = mujer); LabResultados usa M/F."""
    r = await sincronizar_alumnos(db, [alumno("S00000001", CURP_A, sexo="H"),
                                       alumno("S00000002", CURP_B, sexo="M")])
    assert not r["conflictos"]
    assert (await resolver_folio(db, "S00000001")).sexo == "M"   # hombre
    assert (await resolver_folio(db, "S00000002")).sexo == "F"   # mujer


@pytest.mark.asyncio
async def test_sexo_que_no_coincide_con_la_curp_se_reporta(db):
    r = await sincronizar_alumnos(db, [alumno("S00000001", CURP_A, sexo="M")])   # CURP dice H
    assert r["creados"] == 1
    assert any("sexo" in c["motivo"] for c in r["conflictos"])


@pytest.mark.asyncio
async def test_alumno_sin_apellido_paterno_usa_el_materno(db):
    r = await sincronizar_alumnos(db, [alumno(primer_apellido=None, segundo_apellido="UNICO")])
    assert r["creados"] == 1
    assert (await resolver_folio(db, "S00000001")).apellido == "UNICO"


@pytest.mark.asyncio
async def test_regla_de_fecha_de_toma(db):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")
    # 1a muestra: fecha de evaluación aunque el archivo traiga otra fecha
    assert await fecha_toma_tamiz(db, p, date(2026, 10, 24)) == date(2026, 10, 19)
    assert await fecha_toma_tamiz(db, p, None) == date(2026, 10, 19)
    # 2a muestra (ventana 07-ene-2027 en adelante): fecha del archivo
    assert await fecha_toma_tamiz(db, p, date(2027, 1, 12)) == date(2027, 1, 12)
    # alumno sin evaluación capturada: fecha del archivo
    await sincronizar_alumnos(db, [alumno("S00000002", CURP_B, fecha_evaluacion=None)])
    q = await resolver_folio(db, "S00000002")
    assert await fecha_toma_tamiz(db, q, date(2026, 10, 24)) == date(2026, 10, 24)


@pytest.mark.asyncio
async def test_tira_y_vitros_por_folio_caen_en_la_misma_visita(db):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")

    # 1) tira (procesada 3 días después de la evaluación): ALB 30, CRE 150 -> ACR 20
    lote = await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "150", "30")]), "tira.csv", 1)
    assert lote.registros_exitosos == 1 and lote.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))] == (150.0, "tira_uc1000")
    assert v[("ALBOR", date(2026, 10, 19))] == (30.0, "tira_uc1000")
    assert v[("ACR", date(2026, 10, 19))][0] == pytest.approx(20.0)

    # 2) Vitros confirma la creatinina (otra fecha de proceso): reemplaza a la tira y recalcula el ACR
    lote2 = Lote(nombre="vitros.xlsx", descripcion="t", usuario_id=1, estado="procesando",
                 total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote2)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-26", "Número": "S00000001", "Nombre del Paciente": None,
                        "Apellidos": None, "NTS": None, "CRE01": "120"}])
    lote2 = await process_horizontal_excel(db, df, lote2)
    assert lote2.registros_exitosos == 1 and lote2.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))] == (120.0, "vitros")
    assert v[("ACR", date(2026, 10, 19))][0] == pytest.approx(25.0)
    assert not any(f != date(2026, 10, 19) for (_, f) in v)          # una sola visita
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1   # no se crearon pacientes por nombre


@pytest.mark.asyncio
async def test_folio_desconocido_da_error_y_no_crea_pacientes(db):
    lote = await process_uc1000_csv(db, csv_tira([("S99999999", "22/10/2026", "100", "10")]), "tira.csv", 1)
    assert lote.registros_error == 1 and "S99999999" in lote.log_errores

    lote2 = Lote(nombre="v.xlsx", descripcion="t", usuario_id=1, estado="procesando",
                 total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote2)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-26", "Número": "S99999999", "Nombre del Paciente": "X",
                        "Apellidos": "Y", "NTS": None, "CRE01": "100"}])
    lote2 = await process_horizontal_excel(db, df, lote2)
    assert lote2.registros_error == 1
    assert (await db.execute(select(Paciente))).scalars().all() == []


@pytest.mark.asyncio
async def test_servicio_externo_sigue_resolviendo_por_peticion(db):
    """Regresión: el ID 17 + petición del servicio externo no cambia."""
    p = Paciente(identificacion="SYN-TEST", nombre="EXTERNO", apellido="PRUEBA")
    db.add(p)
    await db.flush()
    lote = Lote(nombre="v.xlsx", descripcion="t", usuario_id=1, estado="completado",
                total_registros=1, registros_exitosos=1, registros_error=0)
    db.add(lote)
    await db.flush()
    pr = Prueba(codigo="CRTS", nombre="CRTS", categoria="Química Clínica", unidad="", activa=True)
    db.add(pr)
    await db.flush()
    db.add(Resultado(lote_id=lote.id, paciente_id=p.id, prueba_id=pr.id, valor=0.8,
                     fecha_toma=date(2026, 9, 18), fecha_resultado=date(2026, 9, 18),
                     observaciones="Petición No. 99921732", fuente="vitros", interpretacion="normal"))
    await db.flush()

    res = await process_uc1000_csv(db, csv_tira([("1799921732", "18/09/2026", "100", "10")]), "tira.csv", 1)
    assert res.registros_exitosos == 1 and res.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 9, 18))] == (100.0, "tira_uc1000")


@pytest.mark.asyncio
async def test_realinea_fechas_cuando_llega_la_evaluacion_despues(db):
    # llega el alumno sin evaluación capturada y se carga una tira con la fecha del archivo
    await sincronizar_alumnos(db, [alumno(fecha_evaluacion=None)])
    p = await resolver_folio(db, "S00000001")
    await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "100", "10")]), "tira.csv", 1)
    assert all(f == date(2026, 10, 22) for (_, f) in await valores(db, p.id))

    # después se captura la evaluación (19-oct): los resultados de la 1a muestra se mueven a esa fecha
    r = await sincronizar_alumnos(db, [alumno(fecha_evaluacion="2026-10-19")])
    assert r["fechas_realineadas"] == 3 and r["fechas_en_conflicto"] == 0
    assert all(f == date(2026, 10, 19) for (_, f) in await valores(db, p.id))


@pytest.mark.asyncio
async def test_endpoint_requiere_autenticacion_y_acepta_clave_de_sistema(client):
    from app.config import get_settings
    body = {"campana": {"ciclo": "2026-2027"}, "alumnos": [alumno("S00000077", "TEST030303HASCCC03")]}
    assert (await client.post("/api/integraciones/tamiz/alumnos", json=body)).status_code == 401
    r = await client.post("/api/integraciones/tamiz/alumnos", json=body,
                          headers={"Authorization": get_settings().SYSTEM_API_KEY})
    assert r.status_code == 200, r.text
    assert r.json()["creados"] + r.json()["actualizados"] + r.json()["sin_cambios"] == 1


@pytest.mark.asyncio
async def test_listado_de_pacientes_paginado_y_buscable_por_folio(client, auth_headers):
    from app.config import get_settings
    alumnos = [alumno(f"S9000000{i}", f"TEST0{i}0{i}0{i}HASDDD0{i}") for i in range(1, 4)]
    r = await client.post("/api/integraciones/tamiz/alumnos", json={"alumnos": alumnos},
                          headers={"Authorization": get_settings().SYSTEM_API_KEY})
    assert r.status_code == 200, r.text

    r = await client.get("/api/pacientes", params={"search": "S9000000", "limit": 2}, headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["x-total-count"] == "3"
    assert len(r.json()) == 2 and r.json()[0]["folio_tamiz"].startswith("S9000000")

    r = await client.get("/api/pacientes", params={"search": "S90000002"}, headers=auth_headers)
    assert r.headers["x-total-count"] == "1"
