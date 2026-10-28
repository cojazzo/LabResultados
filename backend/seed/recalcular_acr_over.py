"""
Recalcula el ACR de las visitas con albúmina de tira en "Over" (> 150 mg/L) que se cargaron antes de
que existiera la regla de cota inferior (ver app/utils/acr.py). No toca visitas con albúmina Vitros.

Uso (dentro del contenedor del backend):
    python seed/recalcular_acr_over.py            # simulación: lista lo que haría y hace rollback
    python seed/recalcular_acr_over.py --real     # guarda los cambios
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Prueba, Resultado  # noqa: E402
from app.services.uc1000_parser import (  # noqa: E402
    CODIGO_ACR, CODIGO_ALB, CODIGO_CRE, FUENTE_TIRA, calculate_acr_for_patient,
)


async def main(real: bool):
    async with AsyncSessionLocal() as db:
        pruebas = {p.codigo: p for p in (await db.execute(
            select(Prueba).where(Prueba.codigo.in_([CODIGO_ALB, CODIGO_CRE, CODIGO_ACR])))).scalars().all()}
        faltan = {CODIGO_ALB, CODIGO_CRE, CODIGO_ACR} - set(pruebas)
        if faltan:
            sys.exit(f"Faltan pruebas en el catálogo: {sorted(faltan)}")

        over = (await db.execute(
            select(Resultado).where(
                Resultado.prueba_id == pruebas[CODIGO_ALB].id,
                Resultado.fuente == FUENTE_TIRA,
                Resultado.valor.is_(None),
                Resultado.valor_texto.ilike("%over%"),
            ))).scalars().all()
        print(f"{len(over)} visitas con albúmina de tira en 'over'{'' if real else ' [SIMULACIÓN]'}")

        cambios = 0
        for alb in over:
            acr = await calculate_acr_for_patient(
                db, alb.paciente_id, alb.fecha_toma, alb.lote_id,
                pruebas[CODIGO_ALB], pruebas[CODIGO_CRE], pruebas[CODIGO_ACR])
            estado = f"ACR > {acr:g} mg/g" if acr is not None else "sin ACR (creatinina diluida o ausente)"
            cambios += acr is not None
            print(f"  paciente {alb.paciente_id}  {alb.fecha_toma}  -> {estado}")

        if real:
            await db.commit()
            print(f"Guardado: {cambios} ACR como cota inferior.")
        else:
            await db.rollback()
            print(f"Simulación terminada ({cambios} ACR se guardarían). Nada se guardó; usa --real.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    asyncio.run(main(ap.parse_args().real))
