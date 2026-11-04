"""
Vincula IDs de petición del servicio externo con pacientes, para que las filas de la tira (UC-1000 manda
"17" + petición, ej. 1799922201) se carguen en su perfil aunque no exista Excel de Vitros (no se pidió creatinina).

Uso (dentro del contenedor del backend):
    python seed/vincular_peticiones.py --mapa 99922201=GULD111210MMNZNVA7,99922200=GULG180120MMNZNDA1
    python seed/vincular_peticiones.py --mapa-archivo - [--real] < vinculos.txt     (una "petición=CURP" por línea)
Sin --real es una simulación (hace rollback). El destino es la CURP (o folio) del paciente.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Paciente  # noqa: E402
from app.services.peticiones import vincular_peticion  # noqa: E402


async def vincular(db, mapa: dict, imprimir=print) -> Counter:
    cuenta = Counter()
    for peticion, ident in mapa.items():
        paciente = (await db.execute(select(Paciente).where(
            (Paciente.identificacion == ident) | (Paciente.folio_tamiz == ident)))).scalars().first()
        if not paciente:
            imprimir(f"  {peticion}: no existe un paciente con '{ident}'")
            cuenta["paciente no encontrado"] += 1
            continue
        estado = await vincular_peticion(db, peticion, paciente, "manual")
        imprimir(f"  {peticion} -> paciente {paciente.id} ({paciente.nombre} {paciente.apellido}): {estado}")
        cuenta[estado] += 1
    return cuenta


async def main(real: bool, mapa: dict):
    async with AsyncSessionLocal() as db:
        cuenta = await vincular(db, mapa)
        print(f"{'' if real else '[SIMULACIÓN] '}Resumen: {dict(cuenta)}")
        if real:
            await db.commit()
            print("Guardado.")
        else:
            await db.rollback()
            print("Simulación terminada. Nada se guardó; usa --real.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--mapa", default="", help="petición=CURP separados por coma")
    ap.add_argument("--mapa-archivo", default="", help="archivo (o - para stdin) con una línea petición=CURP")
    args = ap.parse_args()
    pares = [x for x in args.mapa.split(",") if x.strip()]
    if args.mapa_archivo:
        fuente = sys.stdin if args.mapa_archivo == "-" else open(args.mapa_archivo, encoding="utf-8")
        pares += [ln.split("#")[0].strip() for ln in fuente if ln.split("#")[0].strip()]
    equivalencias = dict(par.split("=", 1) for par in pares)
    asyncio.run(main(args.real, {k.strip(): v.strip().upper() for k, v in equivalencias.items()}))
