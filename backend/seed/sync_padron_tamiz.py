"""
Carga inicial (o re-sincronización) del padrón de tamiz-escolar en LabResultados.

Uso (dentro del contenedor del backend):
    python seed/sync_padron_tamiz.py /tmp/padron_tamiz.jsonl [--ciclo 2026-2027] [--dry-run]

El archivo es JSON Lines: un alumno por línea, con los campos de AlumnoTamiz
(ver app/routes/integraciones.py). Usa la misma lógica que POST /api/integraciones/tamiz/alumnos,
es idempotente y confirma por lotes de 500. Con --dry-run procesa todo y hace rollback al final.
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal  # noqa: E402
from app.services.tamiz_sync import CICLO_DEFAULT, sincronizar_alumnos  # noqa: E402

LOTE = 500
SUMAS = ["recibidos", "creados", "actualizados", "sin_cambios", "curp_asignada", "curp_corregida",
         "fechas_realineadas", "fechas_en_conflicto", "inscritos_nuevos"]


async def main(ruta: str, ciclo: str, dry_run: bool):
    with open(ruta, encoding="utf-8") as f:
        alumnos = [json.loads(linea) for linea in f if linea.strip()]
    total = {k: 0 for k in SUMAS}
    conflictos = []
    print(f"{len(alumnos)} alumnos en {ruta} (ciclo {ciclo}){' [DRY-RUN]' if dry_run else ''}")

    async with AsyncSessionLocal() as db:
        for i in range(0, len(alumnos), LOTE):
            lote = alumnos[i:i + LOTE]
            r = await sincronizar_alumnos(db, lote, ciclo=ciclo, total_padron=len(alumnos))
            for k in SUMAS:
                total[k] += r[k]
            conflictos += r["conflictos"]
            if not dry_run:
                await db.commit()
            print(f"  lote {i // LOTE + 1}: {i + len(lote)}/{len(alumnos)}", flush=True)
        if dry_run:
            await db.rollback()

    print("\nRESUMEN:", json.dumps(total, ensure_ascii=False))
    print(f"CONFLICTOS: {len(conflictos)}")
    for c in conflictos[:30]:
        print("  ", c)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("archivo")
    ap.add_argument("--ciclo", default=CICLO_DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.archivo, args.ciclo, args.dry_run))
