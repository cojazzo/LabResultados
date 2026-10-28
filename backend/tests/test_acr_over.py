"""ACR cuando la albúmina de la tira sale "Over" (> 150 mg/L): se guarda como cota inferior."""
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select

from app.models import Lote, Prueba, Resultado
from app.services.excel_parser import process_horizontal_excel
from app.services.pdf_generator import get_kdigo_classification
from app.services.tamiz_sync import resolver_folio, sincronizar_alumnos
from app.services.uc1000_parser import process_uc1000_csv
from app.utils.acr import cota_acr, es_cota, texto_cota
from tests.test_tamiz_integration import alumno, csv_tira, db  # noqa: F401  (db es fixture)


async def acr_de(db, paciente_id):
    res = await db.execute(
        select(Resultado).join(Prueba, Prueba.id == Resultado.prueba_id)
        .where(Resultado.paciente_id == paciente_id, Prueba.codigo == "ACR")
    )
    return res.scalars().all()


def test_cota_acr_por_nivel_de_creatinina():
    assert cota_acr(50) == 300.0
    assert cota_acr(100) == 150.0
    assert cota_acr(200) == 75.0
    assert cota_acr(300) == 50.0
    assert cota_acr(10) is None      # "dilute": repetir la muestra
    assert cota_acr(None) is None
    assert texto_cota(150.0) == ">150" and es_cota(">150") and not es_cota("over") and not es_cota(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("cre,cota", [("50", 300.0), ("100", 150.0), ("200", 75.0), ("300", 50.0)])
async def test_over_guarda_acr_como_cota_positiva(db, cre, cota):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")

    lote = await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", cre, "over")]), "tira.csv", 1)
    assert lote.registros_exitosos == 1 and lote.registros_error == 0

    (acr,) = await acr_de(db, p.id)
    assert float(acr.valor) == cota and acr.valor_texto == f">{cota:g}"
    assert acr.fecha_toma == date(2026, 10, 19) and acr.fuente == "tira_uc1000"
    assert acr.interpretacion in ("alto", "critico_alto")
    assert "pendiente de confirmar" in acr.observaciones


@pytest.mark.asyncio
async def test_over_con_creatinina_diluida_no_genera_acr(db):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")
    await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "10", "over")]), "tira.csv", 1)
    assert await acr_de(db, p.id) == []


@pytest.mark.asyncio
async def test_albumina_vitros_reemplaza_la_cota_por_el_acr_exacto(db):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")
    await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "100", "over")]), "tira.csv", 1)

    lote2 = Lote(nombre="vitros.xlsx", descripcion="t", usuario_id=1, estado="procesando",
                 total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote2)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-26", "Número": "S00000001", "Nombre del Paciente": None,
                        "Apellidos": None, "NTS": None, "ALBOR": "400"}])
    await process_horizontal_excel(db, df, lote2)

    (acr,) = await acr_de(db, p.id)
    assert float(acr.valor) == pytest.approx(400.0)   # 400 mg/L ÷ 100 mg/dL × 100
    assert acr.valor_texto is None and not es_cota(acr.valor_texto)


def test_kdigo_con_cota_es_al_menos_a2():
    k = get_kdigo_classification(None, 150.0, acr_es_cota=True)
    assert k["a_cat"] == "A2" and k["a_label"] == "≥A2"
    assert k["riesgo"] != "Normal" and "albúmina cuantitativa" in k["recomendacion"]
    # cota 300 significa ACR > 300 -> A3
    assert get_kdigo_classification(None, 300.0, acr_es_cota=True)["a_cat"] == "A3"
    # una cota nunca se clasifica como A1, aunque el número fuera bajo
    assert get_kdigo_classification(None, 20.0, acr_es_cota=True)["a_cat"] == "A2"
    # sin cota todo sigue igual
    k = get_kdigo_classification(None, 20.0)
    assert k["a_cat"] == "A1" and k["a_label"] == "A1"
    assert get_kdigo_classification(None, 300.0)["a_cat"] == "A2"
