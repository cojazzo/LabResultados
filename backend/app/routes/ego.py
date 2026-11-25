"""
Examen General de Orina (EGO).

Cualquier usuario (técnico, químico o administrador) captura el examen físico y microscópico (y el químico
mientras la tira no lo llene) de las personas con tira del día. Al guardar, el examen toma folio y su PDF queda
disponible. El químico que realizó el examen (autor del formato que el técnico transcribe) es obligatorio y firma
el reporte. Solo se reporta EGO a quien tiene un examen guardado.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.database import get_db
from app.models import ExamenOrina, Paciente, Quimico, Resultado, User
from app.services.ego_pdf import folio_ego, generar_formato_ego_en_blanco, generar_pdf_ego
from app.utils.ego import CLAVES, CLAVES_QUIMICO, SECCIONES, campos_como_dict
from app.utils.validators import nombre_completo_paciente

router = APIRouter(prefix="/ego", tags=["Examen General de Orina"])

FUENTE_TIRA = "tira_uc1000"


# ── Esquemas ──────────────────────────────────────────────────────────────────

class ValoresEgo(BaseModel):
    color: Optional[str] = Field(None, max_length=100)
    aspecto: Optional[str] = Field(None, max_length=100)
    glucosa: Optional[str] = Field(None, max_length=100)
    bilirrubina: Optional[str] = Field(None, max_length=100)
    cetonas: Optional[str] = Field(None, max_length=100)
    densidad: Optional[str] = Field(None, max_length=100)
    sangre: Optional[str] = Field(None, max_length=100)
    ph: Optional[str] = Field(None, max_length=100)
    proteinas: Optional[str] = Field(None, max_length=100)
    urobilinogeno: Optional[str] = Field(None, max_length=100)
    nitritos: Optional[str] = Field(None, max_length=100)
    leucocitos_esterasa: Optional[str] = Field(None, max_length=100)
    bacterias: Optional[str] = Field(None, max_length=100)
    celulas_epiteliales: Optional[str] = Field(None, max_length=100)
    leucocitos_campo: Optional[str] = Field(None, max_length=100)
    sedimento: Optional[str] = Field(None, max_length=1000)
    observaciones: Optional[str] = Field(None, max_length=2000)

class EgoGuardar(ValoresEgo):
    paciente_id: int
    fecha_toma: date
    # Químico que realizó el examen (escribió el formato que el técnico transcribe): firma el reporte
    # ("Validado por"). Es obligatorio y debe estar activo.
    quimico_id: Optional[int] = None

class EgoResponse(ValoresEgo):
    id: Optional[int] = None
    paciente_id: int
    paciente: str
    identificacion: str
    fecha_toma: date
    quimico_id: Optional[int] = None
    quimico_fuente: Optional[str] = None
    folio: Optional[str] = None

class PendienteItem(BaseModel):
    paciente_id: int
    paciente: str
    identificacion: str
    examen_id: Optional[int] = None
    capturado: bool             # guardado por una persona (tiene folio y PDF)

class PendientesResponse(BaseModel):
    fecha: Optional[date] = None
    items: List[PendienteItem]


# ── Utilidades ────────────────────────────────────────────────────────────────

def _capturado(examen: Optional[ExamenOrina]) -> bool:
    """Una persona guardó el examen (un examen precargado solo desde la tira aún no cuenta)."""
    return bool(examen and examen.capturado_por is not None)


def _limpiar(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None

def _respuesta(paciente: Paciente, fecha_toma: date, examen: Optional[ExamenOrina]) -> EgoResponse:
    valores = {c: getattr(examen, c) for c in CLAVES} if examen else {}
    return EgoResponse(
        id=examen.id if examen else None,
        paciente_id=paciente.id,
        paciente=nombre_completo_paciente(paciente),
        identificacion=paciente.identificacion,
        fecha_toma=fecha_toma,
        quimico_id=examen.quimico_id if examen else None,
        quimico_fuente=examen.quimico_fuente if examen else None,
        # Folio y PDF existen en cuanto una persona guarda el examen
        folio=folio_ego(examen) if _capturado(examen) else None,
        observaciones=examen.observaciones if examen else None,
        **valores,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/campos")
async def get_campos(current_user: User = Depends(get_current_user)):
    """Estudios, unidades y valores de referencia del formato EGO."""
    return {"secciones": [{"clave": k, "nombre": n} for k, n in SECCIONES], "campos": campos_como_dict()}


@router.get("/pendientes", response_model=PendientesResponse)
async def get_pendientes(
    fecha: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Personas con tira UC-1000 (o con EGO ya capturado) en la fecha de toma indicada.
    `capturado` = ya lo guardó una persona. Sin fecha, usa el día más reciente con tira.
    """
    if fecha is None:
        fecha = (await db.execute(
            select(func.max(Resultado.fecha_toma)).where(Resultado.fuente == FUENTE_TIRA)
        )).scalar()
        if fecha is None:
            return PendientesResponse(fecha=None, items=[])

    con_tira = select(Resultado.paciente_id).where(
        Resultado.fecha_toma == fecha, Resultado.fuente == FUENTE_TIRA
    )
    con_ego = select(ExamenOrina.paciente_id).where(ExamenOrina.fecha_toma == fecha)
    pacientes = (await db.execute(
        select(Paciente).where(Paciente.id.in_(con_tira.union(con_ego)))
    )).scalars().all()

    # Un examen precargado desde la tira (que nadie ha guardado) aún no cuenta como capturado
    examenes = {
        e.paciente_id: e
        for e in (await db.execute(select(ExamenOrina).where(ExamenOrina.fecha_toma == fecha))).scalars()
    }
    items = sorted(
        (PendienteItem(
            paciente_id=p.id,
            paciente=nombre_completo_paciente(p),
            identificacion=p.identificacion,
            examen_id=examenes[p.id].id if p.id in examenes else None,
            capturado=_capturado(examenes.get(p.id)),
        ) for p in pacientes),
        key=lambda i: (i.capturado, i.paciente),
    )
    return PendientesResponse(fecha=fecha, items=items)


@router.get("", response_model=EgoResponse)
async def get_ego(
    paciente_id: int,
    fecha_toma: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """EGO de una persona en una fecha; si aún no se captura, devuelve los campos vacíos."""
    paciente = await db.get(Paciente, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    examen = (await db.execute(
        select(ExamenOrina).where(ExamenOrina.paciente_id == paciente_id, ExamenOrina.fecha_toma == fecha_toma)
    )).scalar_one_or_none()
    return _respuesta(paciente, fecha_toma, examen)


@router.put("", response_model=EgoResponse)
async def guardar_ego(
    datos: EgoGuardar,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea o actualiza el EGO de una persona en una fecha de toma. El químico escribe el formato y el técnico lo
    transcribe: cualquier usuario con sesión puede guardarlo, indicando el químico que realizó el examen (activo),
    que aparece como "Validado por" en el reporte. Al guardar toma folio y su PDF queda disponible. Se registra
    quién capturó el examen.
    """
    paciente = await db.get(Paciente, datos.paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    quimico = await db.get(Quimico, datos.quimico_id) if datos.quimico_id else None
    if not quimico or not quimico.activo:
        raise HTTPException(status_code=400, detail="Selecciona el químico (activo) que realizó el examen.")

    examen = (await db.execute(
        select(ExamenOrina).where(
            ExamenOrina.paciente_id == datos.paciente_id, ExamenOrina.fecha_toma == datos.fecha_toma
        )
    )).scalar_one_or_none()
    if not examen:
        examen = ExamenOrina(paciente_id=datos.paciente_id, fecha_toma=datos.fecha_toma, quimico_fuente="manual")
        db.add(examen)

    # Si el químico corrige algún valor de la tira, el examen químico pasa a ser captura manual
    nuevos = {clave: _limpiar(getattr(datos, clave)) for clave in CLAVES}
    if examen.quimico_fuente == "tira_uc1000" and any(getattr(examen, c) != nuevos[c] for c in CLAVES_QUIMICO):
        examen.quimico_fuente = "manual"
    for clave, valor in nuevos.items():
        setattr(examen, clave, valor)
    examen.observaciones = _limpiar(datos.observaciones)
    examen.quimico_id = quimico.id
    examen.capturado_por = current_user.id
    await db.commit()
    await db.refresh(examen)
    return _respuesta(paciente, datos.fecha_toma, examen)


@router.get("/formato")
async def descargar_formato(current_user: User = Depends(get_current_user)):
    """Formato del EGO en blanco (encabezado institucional) para llenarlo a mano; el técnico lo transcribe."""
    return Response(
        content=generar_formato_ego_en_blanco(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="EGO_formato_en_blanco.pdf"'},
    )


@router.get("/{examen_id}/pdf")
async def descargar_pdf(
    examen_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PDF del Examen General de Orina."""
    examen = (await db.execute(
        select(ExamenOrina)
        .options(selectinload(ExamenOrina.paciente), selectinload(ExamenOrina.quimico))
        .where(ExamenOrina.id == examen_id)
    )).scalar_one_or_none()
    if not examen:
        raise HTTPException(status_code=404, detail="Examen no encontrado.")
    if not _capturado(examen):
        raise HTTPException(status_code=409, detail="El examen aún no se ha guardado.")
    pdf = generar_pdf_ego(examen)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{folio_ego(examen)}.pdf"'},
    )
