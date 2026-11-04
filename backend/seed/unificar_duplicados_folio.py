"""
Unifica pacientes duplicados creados por cargas de Excel de Vitros donde el folio de tamiz-escolar
venía en la columna NTS y se guardó como si fuera la identificación (CURP) de un paciente nuevo.

Para cada paciente con identificacion = folio (letra + 8 dígitos) y SIN folio_tamiz, si existe el
paciente del padrón con ese folio_tamiz (o, con --mapa, el folio del padrón que se indique para un
folio capturado con error o de otra escuela):
  - sus resultados pasan al paciente del padrón, con la fecha de toma que corresponde a la campaña
    (fecha de evaluación, igual que en las cargas nuevas);
  - si ya hay un resultado de esa prueba en esa visita, gana Vitros sobre tira; entre iguales se queda
    el que ya estaba en el paciente del padrón;
  - se recalcula el ACR de cada visita afectada;
  - se elimina el paciente duplicado.
Los reportes ya generados del duplicado pasan al paciente del padrón (con sus resultados reapuntados al
resultado que se conserva); quedan con el contenido de cuando se generaron y se actualizan al regenerarlos.
La fusión en sí vive en app/services/pacientes_merge.py (la comparte el alta automática desde formularios).

Uso (dentro del contenedor del backend):
    python seed/unificar_duplicados_folio.py            # simulación: lista y hace rollback
    python seed/unificar_duplicados_folio.py --real     # guarda (respaldo en /tmp/duplicados_folio_respaldo.json)
    python seed/unificar_duplicados_folio.py --mapa S26006185=S26008185,S26019123=S26019125 [--real]
    python seed/unificar_duplicados_folio.py --mapa-archivo - [--real] < equivalencias.txt   (una "origen=destino" por línea)
El destino puede ser un folio del padrón o la identificación (CURP) del paciente que se conserva.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Paciente  # noqa: E402
from app.services.pacientes_merge import (  # noqa: E402
    fila_respaldo as _fila, fusionar_paciente, pruebas_renales, reapuntar_reportes as _reapuntar_reportes,
)

__all__ = ["unificar", "_fila", "_reapuntar_reportes"]   # los usa seed/reunir_visitas_tamiz.py

RESPALDO = "/tmp/duplicados_folio_respaldo.json"
FOLIO_RE = re.compile(r"^[A-Z]\d{8}$")


async def unificar(db, imprimir=print, mapa=None):
    """Unifica los duplicados en la sesión dada (sin confirmar). Devuelve (conteos, respaldo)."""
    cuenta = Counter()
    respaldo = []
    mapa = mapa or {}
    pruebas = await pruebas_renales(db)

    if mapa:
        # con equivalencias explícitas: cualquier paciente indicado (folio mal escrito, SYN, número, etc.)
        duplicados = (await db.execute(select(Paciente).where(Paciente.identificacion.in_(list(mapa))))).scalars().all()
        for faltante in sorted(set(mapa) - {p.identificacion for p in duplicados}):
            imprimir(f"  {faltante}: no existe en LabResultados (nada que unir)")
    else:
        duplicados = [p for p in (await db.execute(
            select(Paciente).where(Paciente.folio_tamiz.is_(None)))).scalars().all()
            if FOLIO_RE.match(p.identificacion or "")]
    imprimir(f"{len(duplicados)} pacientes con identificación tipo folio y sin folio_tamiz")

    for dup in duplicados:
        destino_id = mapa.get(dup.identificacion, dup.identificacion)
        destino = (await db.execute(select(Paciente).where(
            (Paciente.folio_tamiz == destino_id) | (Paciente.identificacion == destino_id),
            Paciente.id != dup.id))).scalars().first()
        if not destino:
            cuenta["sin paciente en el padrón (se deja igual)"] += 1
            imprimir(f"  {dup.identificacion}: no existe en el padrón, se deja igual")
            continue
        respaldo.append(await fusionar_paciente(db, dup, destino, pruebas, cuenta))
    return cuenta, respaldo


async def main(real: bool, mapa: dict):
    async with AsyncSessionLocal() as db:
        cuenta, respaldo = await unificar(db, mapa=mapa)
        print(f"{'' if real else '[SIMULACIÓN] '}Resumen:")
        for k, v in cuenta.items():
            print(f"  {k}: {v}")
        if real:
            with open(RESPALDO, "w", encoding="utf-8") as f:
                json.dump(respaldo, f, ensure_ascii=False)
            await db.commit()
            print(f"Guardado. Respaldo: {RESPALDO}")
        else:
            await db.rollback()
            print("Simulación terminada. Nada se guardó; usa --real.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--mapa", default="", help="origen=destino separados por coma")
    ap.add_argument("--mapa-archivo", default="", help="archivo (o - para stdin) con una línea origen=destino")
    args = ap.parse_args()
    pares = [x for x in args.mapa.split(",") if x.strip()]
    if args.mapa_archivo:
        fuente = sys.stdin if args.mapa_archivo == "-" else open(args.mapa_archivo, encoding="utf-8")
        pares += [ln.split("#")[0].strip() for ln in fuente if ln.split("#")[0].strip()]
    equivalencias = dict(par.split("=", 1) for par in pares)
    asyncio.run(main(args.real, {k.strip(): v.strip() for k, v in equivalencias.items()}))
