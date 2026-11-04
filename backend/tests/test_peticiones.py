"""Vínculo petición -> paciente para filas de la tira sin Vitros. Datos sintéticos."""
import os
import sys
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select

from app.models import Lote, Paciente, Peticion
from app.services.excel_parser import process_horizontal_excel
from app.services.peticiones import normalizar_peticion, vincular_peticion
from app.services.uc1000_parser import process_uc1000_csv
from tests.test_tamiz_integration import csv_tira, db, valores  # noqa: F401  (db es fixture)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
from vincular_peticiones import vincular  # noqa: E402

CURP_1 = "TEST010101HASAAA01"
CURP_2 = "TEST020202MASBBB02"


def test_normalizar_peticion():
    assert normalizar_peticion("99922201") == "99922201"
    assert normalizar_peticion("1799922201") == "99922201"       # con modificador del UC-1000
    assert normalizar_peticion("99922201.0") == "99922201"       # Excel
    assert normalizar_peticion(" 99922201 ") == "99922201"
    assert normalizar_peticion("S26136937") is None
    assert normalizar_peticion("9992220") is None and normalizar_peticion(None) is None


async def paciente(db, curp, nombre="ANA"):
    p = Paciente(identificacion=curp, nombre=nombre, apellido="PRUEBA", origen="servicio_externo")
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_tira_sin_vitros_se_carga_en_el_perfil_vinculado(db):
    p = await paciente(db, CURP_1)
    # sin vínculo ni Vitros: error con instrucciones
    lote = await process_uc1000_csv(db, csv_tira([("1799922201", "04/11/2026", "100", "30")]), "tira.csv", 1)
    assert lote.registros_error == 1 and "vincula la petición" in lote.log_errores.replace("\\u00f3", "ó")

    # con vínculo: se carga y calcula el ACR
    cuenta = await vincular(db, {"99922201": CURP_1}, imprimir=lambda *_: None)
    await db.commit()
    assert cuenta["vinculada"] == 1
    lote = await process_uc1000_csv(db, csv_tira([("1799922201", "04/11/2026", "100", "30")]), "tira.csv", 1)
    assert lote.registros_exitosos == 1 and lote.registros_error == 0
    v = await valores(db, p.id)
    assert v[("ALBOR", date(2026, 11, 4))] == (30.0, "tira_uc1000")
    assert v[("ACR", date(2026, 11, 4))][0] == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_vinculos_idempotentes_y_con_conflicto(db):
    a, b = await paciente(db, CURP_1), await paciente(db, CURP_2, "BEA")
    assert await vincular_peticion(db, "99922201", a) == "vinculada"
    assert await vincular_peticion(db, "99922201", a) == "ya_vinculada"
    assert await vincular_peticion(db, "99922201", b) == "conflicto"          # no se cambia de dueño
    assert await vincular_peticion(db, "123", a) == "formato_invalido"
    assert (await db.execute(select(Peticion))).scalar_one().paciente_id == a.id


@pytest.mark.asyncio
async def test_el_excel_de_vitros_registra_la_peticion_para_la_tira(db):
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-11-04", "Número": "99922205", "Nombre del Paciente": "ANA",
                        "Apellidos": "PRUEBA", "NTS": CURP_1, "CRE01": "120"}])
    await process_horizontal_excel(db, df, lote)
    (pet,) = (await db.execute(select(Peticion))).scalars().all()
    assert pet.id_peticion == "99922205" and pet.fuente == "vitros"
    # la tira con esa petición encuentra al paciente
    lote2 = await process_uc1000_csv(db, csv_tira([("1799922205", "04/11/2026", "100", "30")]), "t.csv", 1)
    assert lote2.registros_exitosos == 1 and lote2.registros_error == 0


@pytest.mark.asyncio
async def test_endpoint_vincula_con_autenticacion(client):
    from app.config import get_settings
    from tests.test_forms_alta_automatica import respuesta
    headers = {"Authorization": get_settings().SYSTEM_API_KEY}
    await client.post("/api/integraciones/forms/respuestas", headers=headers,
                      json={"respuestas": [{"id_respuesta": "x1", "campos": respuesta()}]})
    body = {"vinculos": [{"id_peticion": "99922201", "identificacion": "TEST030303HASCCC03"},
                         {"id_peticion": "99922299", "identificacion": "NOEXISTE00000000000"}]}
    assert (await client.post("/api/integraciones/peticiones", json=body)).status_code == 401
    r = await client.post("/api/integraciones/peticiones", json=body, headers=headers)
    assert r.status_code == 200, r.text
    estados = {v["id_peticion"]: v["estado"] for v in r.json()["vinculos"]}
    assert estados == {"99922201": "vinculada", "99922299": "paciente_no_encontrado"}
