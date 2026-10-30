"""
Reúne en una sola visita las mediciones de alumnos del padrón (campaña de secundarias) que quedaron
en fechas distintas: típicamente la tira en la fecha de evaluación y el Vitros en la fecha del archivo
(cuando el alumno se identificó por CURP en vez de por folio).

Para cada resultado de un alumno con folio_tamiz, la fecha que le corresponde es la de
fecha_toma_tamiz() (fecha de evaluación en la primera muestra; la segunda muestra no se toca). Si ya
existe esa prueba en esa fecha, Vitros gana sobre tira y entre iguales se conserva el que ya estaba.
Solo mueve resultados a menos de 45 días de su fecha correcta. Recalcula el ACR de las visitas
afectadas y reapunta los reportes ya generados al resultado que se conserva.

Uso (dentro del contenedor del backend):
    python seed/reunir_visitas_tamiz.py            # simulación: cuenta y hace rollback
    python seed/reunir_visitas_tamiz.py --real     # guarda (respaldo en /tmp/reunir_visitas_respaldo.json)
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Paciente, Prueba, Resultado  # noqa: E402
from app.services.tamiz_sync import fecha_toma_tamiz  # noqa: E402
from app.services.uc1000_parser import (  # noqa: E402
    CODIGO_ACR, CODIGO_ALB, CODIGO_CRE, FUENTE_VITROS, calculate_acr_for_patient,
)
from unificar_duplicados_folio import _fila, _reapuntar_reportes  # noqa: E402

RESPALDO = "/tmp/reunir_visitas_respaldo.json"
VENTANA_DIAS = 45


async def reunir(db):
    """Reúne las visitas en la sesión dada (sin confirmar). Devuelve (conteos, respaldo)."""
    cuenta = Counter()
    respaldo = []
    pruebas = {p.codigo: p for p in (await db.execute(
        select(Prueba).where(Prueba.codigo.in_([CODIGO_ALB, CODIGO_CRE, CODIGO_ACR])))).scalars().all()}

    filas = (await db.execute(
        select(Resultado, Paciente).join(Paciente, Paciente.id == Resultado.paciente_id)
        .where(Paciente.folio_tamiz.is_not(None)))).all()
    por_paciente = defaultdict(list)
    for r, p in filas:
        por_paciente[p.id].append((r, p))

    for pid, items in por_paciente.items():
        if len({r.fecha_toma for r, _ in items}) < 2:
            continue
        paciente = items[0][1]
        visitas = set()
        for r, _ in sorted(items, key=lambda x: x[0].fecha_toma):
            destino = await fecha_toma_tamiz(db, paciente, r.fecha_toma)
            if destino == r.fecha_toma:
                continue
            if abs((destino - r.fecha_toma).days) > VENTANA_DIAS:
                cuenta["fuera de ventana (no se toca)"] += 1
                continue
            existente = (await db.execute(select(Resultado).where(
                Resultado.paciente_id == pid, Resultado.prueba_id == r.prueba_id,
                Resultado.fecha_toma == destino, Resultado.id != r.id))).scalars().first()
            respaldo.append(_fila(r))
            lote_id = r.lote_id
            if existente is None:
                r.fecha_toma = destino
                cuenta["resultados movidos a la visita correcta"] += 1
            elif r.fuente == FUENTE_VITROS and existente.fuente != FUENTE_VITROS:
                for campo in ("valor", "valor_texto", "interpretacion", "fuente", "lote_id", "observaciones"):
                    setattr(existente, campo, getattr(r, campo))
                await _reapuntar_reportes(db, r.id, existente.id)
                await db.delete(r)
                cuenta["Vitros reemplaza a tira"] += 1
            else:
                await _reapuntar_reportes(db, r.id, existente.id)
                await db.delete(r)
                cuenta["resultado repetido descartado"] += 1
            visitas.add((destino, lote_id))
            await db.flush()
        for fecha, lote_id in visitas:
            await calculate_acr_for_patient(db, pid, fecha, lote_id, pruebas[CODIGO_ALB], pruebas[CODIGO_CRE],
                                            pruebas[CODIGO_ACR])
        if visitas:
            cuenta["alumnos reunidos"] += 1
    return cuenta, respaldo


async def main(real: bool):
    async with AsyncSessionLocal() as db:
        cuenta, respaldo = await reunir(db)
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
    asyncio.run(main(ap.parse_args().real))
