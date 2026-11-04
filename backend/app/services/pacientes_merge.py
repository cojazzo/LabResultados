"""
Fusión de perfiles de paciente duplicados.

Mueve los resultados (y reportes ya generados) de un paciente duplicado al paciente que se conserva,
con la misma regla de fechas que las cargas de campaña, resolviendo choques con la jerarquía
Vitros > tira, recalcula el ACR de las visitas afectadas y elimina el duplicado.
Usado por el script seed/unificar_duplicados_folio.py y por el alta automática desde formularios.
"""
from collections import Counter
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CampanaPaciente, Paciente, Peticion, Prueba, ReporteGenerado, ReporteResultado, Resultado,
)
from app.services.tamiz_sync import fecha_toma_tamiz
from app.services.uc1000_parser import (
    CODIGO_ACR, CODIGO_ALB, CODIGO_CRE, FUENTE_VITROS, calculate_acr_for_patient,
)


def fila_respaldo(r: Resultado) -> dict:
    return {
        "id": r.id, "paciente_id": r.paciente_id, "prueba_id": r.prueba_id, "lote_id": r.lote_id,
        "valor": str(r.valor) if r.valor is not None else None, "valor_texto": r.valor_texto,
        "interpretacion": r.interpretacion, "fecha_toma": str(r.fecha_toma), "fuente": r.fuente,
        "observaciones": r.observaciones,
    }


async def reapuntar_reportes(db: AsyncSession, resultado_viejo: int, resultado_nuevo: int):
    await db.execute(update(ReporteResultado).where(ReporteResultado.resultado_id == resultado_viejo)
                     .values(resultado_id=resultado_nuevo))


async def pruebas_renales(db: AsyncSession) -> dict:
    return {p.codigo: p for p in (await db.execute(
        select(Prueba).where(Prueba.codigo.in_([CODIGO_ALB, CODIGO_CRE, CODIGO_ACR])))).scalars().all()}


async def fusionar_paciente(db: AsyncSession, dup: Paciente, destino: Paciente,
                            pruebas: Optional[dict] = None, cuenta: Optional[Counter] = None) -> dict:
    """
    Fusiona `dup` en `destino` (sin confirmar la transacción). Devuelve el respaldo de lo que movió:
    {"duplicado": {...}, "resultados": [...], "reportes": [...]}.
    """
    cuenta = cuenta if cuenta is not None else Counter()
    pruebas = pruebas if pruebas is not None else await pruebas_renales(db)

    resultados = (await db.execute(select(Resultado).where(Resultado.paciente_id == dup.id))).scalars().all()
    reportes = list((await db.execute(
        select(ReporteGenerado.id).where(ReporteGenerado.paciente_id == dup.id))).scalars().all())
    respaldo = {
        "duplicado": {"id": dup.id, "identificacion": dup.identificacion, "nombre": dup.nombre,
                      "apellido": dup.apellido, "paciente_destino_id": destino.id},
        "resultados": [fila_respaldo(r) for r in resultados],
        "reportes": reportes,
    }

    visitas = set()
    lote_id = resultados[0].lote_id if resultados else None
    for r in resultados:
        fecha = await fecha_toma_tamiz(db, destino, r.fecha_toma)
        existente = (await db.execute(select(Resultado).where(
            Resultado.paciente_id == destino.id, Resultado.prueba_id == r.prueba_id,
            Resultado.fecha_toma == fecha))).scalars().first()
        if existente is None:
            r.paciente_id, r.fecha_toma = destino.id, fecha
            cuenta["resultados movidos"] += 1
        elif r.fuente == FUENTE_VITROS and existente.fuente != FUENTE_VITROS:
            for campo in ("valor", "valor_texto", "interpretacion", "fuente", "lote_id", "observaciones"):
                setattr(existente, campo, getattr(r, campo))
            await reapuntar_reportes(db, r.id, existente.id)
            await db.delete(r)
            cuenta["Vitros reemplaza a tira"] += 1
        else:
            await reapuntar_reportes(db, r.id, existente.id)
            await db.delete(r)
            cuenta["resultado repetido descartado"] += 1
        visitas.add(fecha)
    await db.flush()

    if all(c in pruebas for c in (CODIGO_ALB, CODIGO_CRE, CODIGO_ACR)):
        for fecha in visitas:
            await calculate_acr_for_patient(db, destino.id, fecha, lote_id, pruebas[CODIGO_ALB],
                                            pruebas[CODIGO_CRE], pruebas[CODIGO_ACR])

    if reportes:
        await db.execute(update(ReporteGenerado).where(ReporteGenerado.paciente_id == dup.id)
                         .values(paciente_id=destino.id))
        cuenta["reportes pasados al paciente del padrón"] += len(reportes)
    await db.execute(update(Peticion).where(Peticion.paciente_id == dup.id).values(paciente_id=destino.id))
    await db.execute(delete(CampanaPaciente).where(CampanaPaciente.paciente_id == dup.id))
    await db.delete(dup)
    await db.flush()
    cuenta["pacientes unificados"] += 1
    return respaldo
