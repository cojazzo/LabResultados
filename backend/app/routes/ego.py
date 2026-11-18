"""
Examen General de Orina (EGO).

El técnico o el químico capturan el examen físico y microscópico (y el químico mientras la tira no lo llene)
de las personas con tira del día. Lo que captura un técnico queda "por validar": solo un químico (o administrador)
lo valida, y solo entonces hay folio y PDF. Solo se reporta EGO a quien tiene un examen validado.
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
from app.services.ego_pdf import folio_ego, generar_pdf_ego
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
    # Quién valida el reporte. Obligatorio para un químico o administrador; el técnico no valida
    # (se ignora): lo que captura queda "por validar" hasta que un químico lo revise y lo guarde.
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
    por_validar: bool = False   # capturado por un técnico, a la espera de que un químico lo valide

class PendienteItem(BaseModel):
    paciente_id: int
    paciente: str
    identificacion: str
    examen_id: Optional[int] = None
    capturado: bool             # validado por un químico (tiene folio y PDF)
    por_validar: bool = False

class PendientesResponse(BaseModel):
    fecha: Optional[date] = None
    items: List[PendienteItem]


# ── Utilidades ────────────────────────────────────────────────────────────────

def _es_validador(user: User) -> bool:
    """Un químico o administrador valida el EGO (de él depende que exista el folio y el PDF)."""
    return bool(user.is_superuser or user.rol in ("admin", "quimico"))


def _por_validar(examen: Optional[ExamenOrina]) -> bool:
    """Capturado por una persona (técnico) y sin validación de un químico."""
    return bool(examen and examen.quimico_id is None and examen.capturado_por is not None)

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
        # Folio y PDF solo existen cuando un químico validó el examen
        folio=folio_ego(examen) if examen and examen.quimico_id else None,
        por_validar=_por_validar(examen),
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
    `capturado` = validado por un químico. Sin fecha, usa el día más reciente con tira.
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

    # Un examen precargado desde la tira (sin químico) aún no cuenta como capturado
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
            capturado=p.id in examenes and examenes[p.id].quimico_id is not None,
            por_validar=_por_validar(examenes.get(p.id)),
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
    Crea o actualiza el EGO de una persona en una fecha de toma.

    - Químico o administrador: captura y VALIDA (debe indicar un químico activo); el examen queda con folio y PDF.
    - Técnico: captura los valores, pero no valida. Queda "por validar" hasta que un químico lo revise y lo guarde,
      y no puede modificar un examen que ya validó un químico.
    """
    validador = _es_validador(current_user)
    paciente = await db.get(Paciente, datos.paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado.")
    quimico = None
    if validador:
        quimico = await db.get(Quimico, datos.quimico_id) if datos.quimico_id else None
        if not quimico or not quimico.activo:
            raise HTTPException(status_code=400, detail="Selecciona un químico activo que valide el examen.")

    examen = (await db.execute(
        select(ExamenOrina).where(
            ExamenOrina.paciente_id == datos.paciente_id, ExamenOrina.fecha_toma == datos.fecha_toma
        )
    )).scalar_one_or_none()
    if examen is not None and examen.quimico_id is not None and not validador:
        raise HTTPException(
            status_code=403,
            detail="Este examen ya fue validado por un químico; solo un químico o un administrador puede modificarlo.")
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
    if validador:
        examen.quimico_id = quimico.id
    examen.capturado_por = current_user.id
    await db.commit()
    await db.refresh(examen)
    return _respuesta(paciente, datos.fecha_toma, examen)


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
    if examen.quimico_id is None:
        raise HTTPException(status_code=409, detail="El examen aún no está capturado y validado por un químico.")
    pdf = generar_pdf_ego(examen)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{folio_ego(examen)}.pdf"'},
    )
