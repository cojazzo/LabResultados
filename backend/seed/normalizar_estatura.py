"""
Corrige las estaturas guardadas en METROS (ej. 1.40) pasándolas a CENTÍMETROS (140), que es la unidad que usan
el reporte PDF (TFG pediátrica), el IMC del Excel y la sincronización con tamiz-escolar.

Solo toca valores menores a 3 (nadie mide menos de 3 cm); los demás no se tocan. Guarda un respaldo JSON con
el valor anterior antes de cambiar nada.

Uso (dentro del contenedor del backend):
    python seed/normalizar_estatura.py            # simulación: cuenta y hace rollback
    python seed/normalizar_estatura.py --real     # guarda (respaldo en /tmp/estatura_respaldo.json)
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Paciente  # noqa: E402

RESPALDO = "/tmp/estatura_respaldo.json"


async def normalizar(db):
    """Pasa a cm las estaturas menores a 3 (sin confirmar). Devuelve (conteos, respaldo)."""
    cuenta = Counter()
    respaldo = []
    pacientes = (await db.execute(select(Paciente).where(Paciente.estatura.is_not(None), Paciente.estatura < 3))
                 ).scalars().all()
    for p in pacientes:
        nueva = (Decimal(p.estatura) * 100).quantize(Decimal("0.1"))
        if not (30 <= nueva <= 250):
            cuenta["fuera de rango plausible (no se toca)"] += 1
            continue
        respaldo.append({"paciente_id": p.id, "estatura_anterior": str(p.estatura)})
        p.estatura = nueva
        cuenta["corregidas a cm"] += 1
    return cuenta, respaldo


async def main(real: bool):
    async with AsyncSessionLocal() as db:
        cuenta, respaldo = await normalizar(db)
        print(f"{'' if real else '[SIMULACIÓN] '}Resumen:")
        for k, v in cuenta.items():
            print(f"  {k}: {v}")
        if real:
            with open(RESPALDO, "w", encoding="utf-8") as f:
                json.dump(respaldo, f)
            await db.commit()
            print(f"Guardado. Respaldo: {RESPALDO}")
        else:
            await db.rollback()
            print("Simulación terminada. Nada se guardó; usa --real.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    asyncio.run(main(ap.parse_args().real))
