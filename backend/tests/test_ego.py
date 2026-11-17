"""
Examen General de Orina: lista de pendientes, captura del químico y PDF.
Datos 100% sintéticos, en una fecha propia (2032-02-02).
"""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Lote, Paciente, Prueba, Quimico, Resultado, User

FECHA = "2032-02-02"


@pytest_asyncio.fixture
async def escenario(db_session):
    db = db_session
    pac = (await db.execute(select(Paciente).where(Paciente.identificacion == "EGO-SINT-1"))).scalar_one_or_none()
    if not pac:
        pac = Paciente(identificacion="EGO-SINT-1", nombre="Sintética", apellido="Orina", sexo="F",
                       fecha_nacimiento=date(2000, 5, 5))
        quim = Quimico(nombre_completo="Q.F.B. Sintético Prueba", cedula="EGO-0001", activo=True)
        prueba = (await db.execute(select(Prueba).where(Prueba.codigo == "CRE01"))).scalar_one_or_none()
        if not prueba:
            prueba = Prueba(codigo="CRE01", nombre="Creatinina Urinaria", unidad="mg/dL", categoria="Función Renal")
        lote = Lote(nombre="lote-sintetico-ego")
        db.add_all([pac, quim, prueba, lote])
        await db.flush()
        db.add(Resultado(paciente_id=pac.id, prueba_id=prueba.id, lote_id=lote.id, valor=Decimal("10"),
                         fecha_toma=date(2032, 2, 2), fuente="tira_uc1000", interpretacion="bajo"))
        await db.commit()
    quim = (await db.execute(select(Quimico).where(Quimico.cedula == "EGO-0001"))).scalar_one()
    return {"paciente_id": pac.id, "quimico_id": quim.id}


@pytest.mark.asyncio
async def test_flujo_completo_de_captura(client, auth_headers, escenario):
    # 1. Aparece como pendiente por tener tira ese día
    r = await client.get("/api/ego/pendientes", params={"fecha": FECHA}, headers=auth_headers)
    assert r.status_code == 200
    item = next(i for i in r.json()["items"] if i["paciente_id"] == escenario["paciente_id"])

    # 2. Sin captura, el EGO viene vacío
    r = await client.get("/api/ego", params={"paciente_id": escenario["paciente_id"], "fecha_toma": FECHA},
                         headers=auth_headers)
    assert r.status_code == 200 and r.json()["id"] is None

    # 3. El químico captura físico, químico y microscópico
    datos = {
        "paciente_id": escenario["paciente_id"], "fecha_toma": FECHA, "quimico_id": escenario["quimico_id"],
        "color": "Incoloro", "aspecto": "Transparente", "glucosa": "Negativo", "densidad": "1.000",
        "ph": "5.5", "urobilinogeno": "Normal", "bacterias": "Moderadas", "celulas_epiteliales": "Escasas",
        "leucocitos_campo": "0-2", "sedimento": "  ", "observaciones": "Muestra sintética",
    }
    r = await client.put("/api/ego", json=datos, headers=auth_headers)
    assert r.status_code == 200, r.text
    ego = r.json()
    assert ego["id"] and ego["folio"].startswith("EGO-2032-")
    assert ego["color"] == "Incoloro" and ego["bacterias"] == "Moderadas"
    assert ego["sedimento"] is None  # vacío se guarda como nulo

    # 4. Volver a guardar actualiza el mismo registro
    r = await client.put("/api/ego", json={**datos, "color": "Amarillo"}, headers=auth_headers)
    assert r.json()["id"] == ego["id"] and r.json()["color"] == "Amarillo"

    # 5. Ya figura como capturado
    r = await client.get("/api/ego/pendientes", params={"fecha": FECHA}, headers=auth_headers)
    item = next(i for i in r.json()["items"] if i["paciente_id"] == escenario["paciente_id"])
    assert item["capturado"] and item["examen_id"] == ego["id"]

    # 6. PDF
    r = await client.get(f"/api/ego/{ego['id']}/pdf", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_requiere_quimico_activo(client, auth_headers, escenario):
    r = await client.put("/api/ego", json={
        "paciente_id": escenario["paciente_id"], "fecha_toma": FECHA, "quimico_id": 999999,
    }, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_tecnico_no_puede_capturar(client, db_session, escenario):
    from app.core.security import get_password_hash
    if not (await db_session.execute(select(User).where(User.username == "tecnico-ego"))).scalar_one_or_none():
        db_session.add(User(username="tecnico-ego", email="tecnico-ego@example.test", rol="tecnico",
                            hashed_password=get_password_hash("tecnico-ego-1"), nombre_completo="Técnico Sintético"))
        await db_session.commit()
    login = await client.post("/api/auth/login", data={"username": "tecnico-ego", "password": "tecnico-ego-1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = await client.put("/api/ego", json={
        "paciente_id": escenario["paciente_id"], "fecha_toma": FECHA, "quimico_id": escenario["quimico_id"],
    }, headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_campos_del_formato(client, auth_headers):
    r = await client.get("/api/ego/campos", headers=auth_headers)
    campos = {c["clave"]: c for c in r.json()["campos"]}
    assert campos["ph"]["referencia"] == "5.0 – 8.0"
    assert campos["leucocitos_campo"]["unidades"] == "CPA"
    assert {c["seccion"] for c in campos.values()} == {"fisico", "quimico", "microscopico"}


# ── Examen químico desde la tira UC-1000 ────────────────────────────────────

# Encabezados reales del CSV del UC-1000 (no contienen datos de pacientes)
ENC_GRUPOS = "UC-1000,,,,,,,,,,URO,,,,,,BLD,,,,,,BIL,,,,,,KET,,,,,,GLU,,,,,,PRO,,,,,,,pH,,,,,,NIT,,,,,,LEU,,,,,,S.G,,,,,,CRE,,,,,,ALB,,,,,,P/C,,,,A/C,,,,Reserve,,,,COLOR,,,,CLOUD"
ENC_SUB = "Version,Id,RackNo,RackPos,Series,No,Error,Strip,DATE,TIME," + ",".join(
    ["Exist,Mark,Flag,Conc,R%(1),R%(2)"] * 5 + ["Exist,Mark,Flag,Conc,R%(1),R%(2),R%(3)"]
    + ["Exist,Mark,Flag,Conc,R%(1),R%(2)"] * 6
) + ",Exist,Mark,Flag,Conc,Exist,Mark,Flag,Conc,,,,,Exist,Mark,,Color,"

CURP_TIRA = "SINT000000EGOTIRA1"


def fila_tira(id_, fecha, **flags):
    """Fila sintética: flags={"GLU": ("3+", "500"), "pH": ("6.0", "")…}; CRE/ALB en Conc."""
    import csv as _csv
    from app.services.ego_tira import mapa_columnas
    grupos = next(_csv.reader([ENC_GRUPOS]))
    sub = next(_csv.reader([ENC_SUB]))
    cols = mapa_columnas(grupos, sub)
    row = [""] * len(sub)
    row[1], row[8] = id_, fecha
    for param, (flag, conc) in flags.items():
        row[cols[(param, "Flag")]] = flag
        row[cols[(param, "Conc")]] = conc
    return row


def csv_tira(filas):
    import csv as _csv, io
    out = io.StringIO()
    w = _csv.writer(out)
    w.writerow(next(_csv.reader([ENC_GRUPOS])))
    w.writerow(next(_csv.reader([ENC_SUB])))
    for f in filas:
        w.writerow(f)
    return out.getvalue().encode("utf-8")


def test_columnas_coinciden_con_el_parser_actual():
    """Las columnas por encabezado coinciden con los índices fijos de creatinina y albúmina."""
    import csv as _csv
    from app.services.ego_tira import mapa_columnas
    from app.services.uc1000_parser import IDX_ALB, IDX_CRE
    cols = mapa_columnas(next(_csv.reader([ENC_GRUPOS])), next(_csv.reader([ENC_SUB])))
    assert cols[("CRE", "Conc")] == IDX_CRE and cols[("ALB", "Conc")] == IDX_ALB
    assert cols[("GLU", "Flag")] == 36 and cols[("S.G", "Flag")] == 67


def test_extraer_quimico_formatea_valores():
    import csv as _csv
    from app.services.ego_tira import extraer_quimico, mapa_columnas
    cols = mapa_columnas(next(_csv.reader([ENC_GRUPOS])), next(_csv.reader([ENC_SUB])))
    row = fila_tira("X", "01/01/2033", URO=("normal", ""), BLD=("1+", "0.06"), BIL=(" -", ""),
                    GLU=("*3+", "500"), PRO=("+-", "15"), pH=("5.5", ""), NIT=("*+", ""),
                    LEU=(" -", ""), **{"S.G": ("1.020", "")})
    v = extraer_quimico(row, cols)
    assert v["urobilinogeno"] == "Normal"
    assert v["sangre"] == "1+"              # sin concentración: el formato usa Eri/µL
    assert v["bilirrubina"] == "Negativo"
    assert v["glucosa"] == "3+ (500)"
    assert v["proteinas"] == "± (15)"
    assert v["ph"] == "5.5" and v["densidad"] == "1.020"
    assert v["nitritos"] == "Positivo"
    assert "cetonas" not in v               # vacío en la fila


@pytest.mark.asyncio
async def test_tira_precarga_ego_sin_validarlo(client, auth_headers, db_session, escenario):
    from app.services.uc1000_parser import process_uc1000_csv
    db = db_session
    if not (await db.execute(select(Paciente).where(Paciente.identificacion == CURP_TIRA))).scalar_one_or_none():
        db.add(Paciente(identificacion=CURP_TIRA, nombre="Sintético", apellido="Tira", sexo="M",
                        fecha_nacimiento=date(2011, 3, 3)))
        await db.commit()
    pac = (await db.execute(select(Paciente).where(Paciente.identificacion == CURP_TIRA))).scalar_one()

    fila = fila_tira(CURP_TIRA, "03/03/2033", GLU=("*2+", "250"), pH=("6.0", ""), CRE=("", "100"), ALB=("", "10"),
                     **{"S.G": ("1.015", "")})
    lote = await process_uc1000_csv(db, csv_tira([fila]), "sintetico.csv", None)
    assert lote.registros_exitosos == 1, lote.log_errores

    # Precargado, pero sin químico: no cuenta como capturado y no hay PDF
    r = await client.get("/api/ego", params={"paciente_id": pac.id, "fecha_toma": "2033-03-03"}, headers=auth_headers)
    ego = r.json()
    assert ego["glucosa"] == "2+ (250)" and ego["ph"] == "6.0" and ego["densidad"] == "1.015"
    assert ego["quimico_fuente"] == "tira_uc1000" and ego["folio"] is None
    r = await client.get("/api/ego/pendientes", params={"fecha": "2033-03-03"}, headers=auth_headers)
    assert not next(i for i in r.json()["items"] if i["paciente_id"] == pac.id)["capturado"]
    assert (await client.get(f"/api/ego/{ego['id']}/pdf", headers=auth_headers)).status_code == 409

    # El químico valida sin cambiar la tira: sigue siendo de la tira
    base = {k: ego[k] for k in ("glucosa", "ph", "densidad")}
    r = await client.put("/api/ego", json={"paciente_id": pac.id, "fecha_toma": "2033-03-03",
                                           "quimico_id": escenario["quimico_id"], "color": "Amarillo", **base},
                         headers=auth_headers)
    assert r.json()["quimico_fuente"] == "tira_uc1000" and r.json()["folio"]

    # Corrige la glucosa: pasa a captura manual y una nueva carga de la tira ya no la pisa
    r = await client.put("/api/ego", json={"paciente_id": pac.id, "fecha_toma": "2033-03-03",
                                           "quimico_id": escenario["quimico_id"], **base, "glucosa": "1+"},
                         headers=auth_headers)
    assert r.json()["quimico_fuente"] == "manual"
    await process_uc1000_csv(db, csv_tira([fila]), "sintetico.csv", None)
    r = await client.get("/api/ego", params={"paciente_id": pac.id, "fecha_toma": "2033-03-03"}, headers=auth_headers)
    assert r.json()["glucosa"] == "1+"
