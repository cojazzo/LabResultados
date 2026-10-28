"""
Fija el límite superior de referencia del ACR (30 mg/g, KDIGO A1) en el catálogo y recalcula la
interpretación de los ACR que ya existen (todos estaban en "normal" porque la prueba no tenía rangos).

Solo toca ACR con valor numérico (exactos y cotas ">X"); los de solo texto no se modifican.
Guarda un respaldo JSON con la interpretación anterior antes de cambiar nada.

Uso (dentro del contenedor del backend):
    python seed/corregir_rango_acr.py            # simulación: cuenta los cambios y hace rollback
    python seed/corregir_rango_acr.py --real     # guarda (respaldo en /tmp/acr_interpretacion_previa.json)
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Prueba, Resultado  # noqa: E402
from app.utils.validators import calcular_interpretacion  # noqa: E402

VALOR_MAX_ACR = 30.0
RESPALDO = "/tmp/acr_interpretacion_previa.json"


async def main(real: bool):
    async with AsyncSessionLocal() as db:
        prueba = (await db.execute(select(Prueba).where(Prueba.codigo == "ACR"))).scalar_one()
        print(f"Prueba ACR (id {prueba.id}): valor_max actual = {prueba.valor_max}"
              f"{'' if real else '  [SIMULACIÓN]'}")
        if prueba.valor_max is None:
            prueba.valor_max = VALOR_MAX_ACR
        elif float(prueba.valor_max) != VALOR_MAX_ACR:
            sys.exit(f"valor_max ya es {prueba.valor_max}, no lo sobreescribo.")

        resultados = (await db.execute(
            select(Resultado).where(Resultado.prueba_id == prueba.id, Resultado.valor.is_not(None))
        )).scalars().all()

        cambios = Counter()
        respaldo = []
        for r in resultados:
            nueva = calcular_interpretacion(
                float(r.valor), prueba.valor_min, prueba.valor_max,
                prueba.valor_critico_min, prueba.valor_critico_max)
            if nueva != r.interpretacion:
                cambios[(r.interpretacion, nueva, "cota" if (r.valor_texto or "").startswith(">") else "exacto")] += 1
                respaldo.append({"id": r.id, "interpretacion_previa": r.interpretacion})
                r.interpretacion = nueva

        print(f"{len(resultados)} ACR numéricos revisados, {len(respaldo)} cambiarían:")
        for (antes, despues, tipo), n in sorted(cambios.items()):
            print(f"  {antes} -> {despues}  ({tipo}): {n}")

        if real:
            with open(RESPALDO, "w", encoding="utf-8") as f:
                json.dump({"prueba_id": prueba.id, "valor_max_previo": None, "resultados": respaldo}, f)
            await db.commit()
            print(f"Guardado. Respaldo: {RESPALDO}")
        else:
            await db.rollback()
            print("Simulación terminada. Nada se guardó; usa --real.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    asyncio.run(main(ap.parse_args().real))
