"""Script que corrige estaturas guardadas en metros. Datos sintéticos."""
import os
import sys
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Paciente
from tests.test_tamiz_integration import db  # noqa: F401  (db es fixture)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
from normalizar_estatura import normalizar  # noqa: E402


@pytest.mark.asyncio
async def test_pasa_metros_a_centimetros_y_no_toca_lo_demas(db):
    db.add_all([
        Paciente(identificacion="SYN-A", nombre="A", apellido="X", estatura=Decimal("1.40")),
        Paciente(identificacion="SYN-B", nombre="B", apellido="X", estatura=Decimal("172.00")),
        Paciente(identificacion="SYN-C", nombre="C", apellido="X", estatura=Decimal("0.20")),   # imposible
        Paciente(identificacion="SYN-D", nombre="D", apellido="X", estatura=None),
    ])
    await db.commit()
    cuenta, respaldo = await normalizar(db)
    await db.commit()
    est = {p.identificacion: p.estatura for p in (await db.execute(select(Paciente))).scalars().all()}
    assert est["SYN-A"] == Decimal("140.0") and est["SYN-B"] == Decimal("172.00")
    assert est["SYN-C"] == Decimal("0.20") and est["SYN-D"] is None
    assert cuenta["corregidas a cm"] == 1 and cuenta["fuera de rango plausible (no se toca)"] == 1
    assert respaldo == [{"paciente_id": respaldo[0]["paciente_id"], "estatura_anterior": "1.40"}]
