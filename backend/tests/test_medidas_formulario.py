"""Peso y estatura capturados en el formulario: coma decimal y estatura en metros. Datos sintéticos."""
import pytest
from sqlalchemy import select

from app.models import Paciente
from app.utils.validators import normalizar_estatura_cm, normalizar_peso_kg, parse_decimal
from tests.test_forms_alta_automatica import enviar, respuesta, db  # noqa: F401  (db es fixture)


def test_parse_decimal_acepta_coma_punto_y_unidades():
    assert parse_decimal("1,4") == 1.4
    assert parse_decimal("50 kg") == 50.0
    assert parse_decimal("14años") == 14.0
    assert parse_decimal(1.65) == 1.65
    assert parse_decimal("") is None and parse_decimal(None) is None and parse_decimal("sin dato") is None


def test_estatura_en_metros_se_guarda_en_centimetros():
    assert normalizar_estatura_cm("1,4") == 140.0
    assert normalizar_estatura_cm("1.65") == 165.0
    assert normalizar_estatura_cm(1.1) == 110.0
    assert normalizar_estatura_cm("172") == 172.0          # ya viene en cm
    assert normalizar_estatura_cm("170 cm") == 170.0
    assert normalizar_estatura_cm("14") is None            # fuera de rango plausible
    assert normalizar_estatura_cm("0,2") is None             # 20 cm: imposible
    assert normalizar_estatura_cm(None) is None


def test_peso_plausible():
    assert normalizar_peso_kg("35,5") == 35.5
    assert normalizar_peso_kg("0") is None
    assert normalizar_peso_kg("900") is None


@pytest.mark.asyncio
async def test_formulario_guarda_estatura_en_cm_peso_con_coma_y_correo_normalizado(db):
    await enviar(db, [respuesta(Peso="25,5", Estatura="1,1",
                                **{"Correo electrónico": " Chabela16lin@Gmail.com "})])
    (p,) = (await db.execute(select(Paciente))).scalars().all()
    assert float(p.estatura) == 110.0 and float(p.peso) == 25.5
    assert p.email == "chabela16lin@gmail.com"
