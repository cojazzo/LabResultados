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

Uso (dentro del contenedor del backend):
    python seed/unificar_duplicados_folio.py            # simulación: lista y hace rollback
    python seed/unificar_duplicados_folio.py --real     # guarda (respaldo en /tmp/duplicados_folio_respaldo.json)
    python seed/unificar_duplicados_folio.py --mapa S26006185=S26008185,S26019123=S26019125 [--real]
"""
import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select, update  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import CampanaPaciente, Paciente, Prueba, ReporteGenerado, ReporteResultado, Resultado  # noqa: E402
from app.services.tamiz_sync import fecha_toma_tamiz  # noqa: E402
from app.services.uc1000_parser import (  # noqa: E402
    CODIGO_ACR, CODIGO_ALB, CODIGO_CRE, FUENTE_VITROS, calculate_acr_for_patient,
)

RESPALDO = "/tmp/duplicados_folio_respaldo.json"
FOLIO_RE = re.compile(r"^[A-Z]\d{8}$")


def _fila(r: Resultado) -> dict:
    return {
        "id": r.id, "paciente_id": r.paciente_id, "prueba_id": r.prueba_id, "lote_id": r.lote_id,
        "valor": str(r.valor) if r.valor is not None else None, "valor_texto": r.valor_texto,
        "interpretacion": r.interpretacion, "fecha_toma": str(r.fecha_toma), "fuente": r.fuente,
        "observaciones": r.observaciones,
    }


async def _reapuntar_reportes(db, resultado_viejo: int, resultado_nuevo: int):
    await db.execute(update(ReporteResultado).where(ReporteResultado.resultado_id == resultado_viejo)
                     .values(resultado_id=resultado_nuevo))


async def unificar(db, imprimir=print, mapa=None):
    """Unifica los duplicados en la sesión dada (sin confirmar). Devuelve (conteos, respaldo)."""
    cuenta = Counter()
    respaldo = []
    mapa = mapa or {}
    pruebas = {p.codigo: p for p in (await db.execute(
        select(Prueba).where(Prueba.codigo.in_([CODIGO_ALB, CODIGO_CRE, CODIGO_ACR])))).scalars().all()}

    duplicados = [p for p in (await db.execute(
        select(Paciente).where(Paciente.folio_tamiz.is_(None)))).scalars().all()
        if FOLIO_RE.match(p.identificacion or "") and (not mapa or p.identificacion in mapa)]
    imprimir(f"{len(duplicados)} pacientes con identificación tipo folio y sin folio_tamiz")

    for dup in duplicados:
        real_p = (await db.execute(select(Paciente).where(
            Paciente.folio_tamiz == mapa.get(dup.identificacion, dup.identificacion)))).scalar_one_or_none()
        if not real_p:
            cuenta["sin paciente en el padrón (se deja igual)"] += 1
            imprimir(f"  {dup.identificacion}: no existe en el padrón, se deja igual")
            continue
        reportes = (await db.execute(
            select(ReporteGenerado.id).where(ReporteGenerado.paciente_id == dup.id))).scalars().all()

        resultados = (await db.execute(select(Resultado).where(Resultado.paciente_id == dup.id))).scalars().all()
        respaldo.append({"duplicado": {"id": dup.id, "identificacion": dup.identificacion, "nombre": dup.nombre,
                                       "apellido": dup.apellido, "paciente_destino_id": real_p.id},
                         "resultados": [_fila(r) for r in resultados], "reportes": list(reportes)})
        visitas = set()
        for r in resultados:
            destino = await fecha_toma_tamiz(db, real_p, r.fecha_toma)
            existente = (await db.execute(select(Resultado).where(
                Resultado.paciente_id == real_p.id, Resultado.prueba_id == r.prueba_id,
                Resultado.fecha_toma == destino))).scalars().first()
            if existente is None:
                r.paciente_id, r.fecha_toma = real_p.id, destino
                cuenta["resultados movidos"] += 1
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
            visitas.add(destino)
        await db.flush()

        for fecha in visitas:
            if all(c in pruebas for c in (CODIGO_ALB, CODIGO_CRE, CODIGO_ACR)):
                await calculate_acr_for_patient(
                    db, real_p.id, fecha, resultados[0].lote_id if resultados else None,
                    pruebas[CODIGO_ALB], pruebas[CODIGO_CRE], pruebas[CODIGO_ACR])

        if reportes:
            await db.execute(update(ReporteGenerado).where(ReporteGenerado.paciente_id == dup.id)
                             .values(paciente_id=real_p.id))
            cuenta["reportes pasados al paciente del padrón"] += len(reportes)
        await db.execute(delete(CampanaPaciente).where(CampanaPaciente.paciente_id == dup.id))
        await db.delete(dup)
        await db.flush()
        cuenta["pacientes unificados"] += 1

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
    ap.add_argument("--mapa", default="", help="folio_capturado=folio_padron separados por coma")
    args = ap.parse_args()
    equivalencias = dict(par.split("=", 1) for par in args.mapa.split(",") if par.strip())
    asyncio.run(main(args.real, {k.strip(): v.strip() for k, v in equivalencias.items()}))
