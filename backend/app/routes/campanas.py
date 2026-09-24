import io
import json
import os
import re
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Campana, CampanaPaciente, Paciente, Resultado, ReporteGenerado, User
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

router = APIRouter(prefix="/campanas", tags=["Campañas"])


# ── Schemas ────────────────────────────────────────────────────────────

class CampanaCreate(BaseModel):
    nombre: str
    tipo: str  # secundaria | servicio_externo | campana_externa
    descripcion: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    ubicacion: Optional[str] = None
    direccion: Optional[str] = None
    estado: Optional[str] = "activa"

class CampanaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    ubicacion: Optional[str] = None
    direccion: Optional[str] = None
    estado: Optional[str] = None

class CampanaResponse(BaseModel):
    id: int
    nombre: str
    slug: str
    tipo: str
    descripcion: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    ubicacion: Optional[str] = None
    direccion: Optional[str] = None
    estado: str
    total_pacientes: Optional[int] = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CampanaPacienteResponse(BaseModel):
    id: int
    paciente_id: int
    nombre: str
    apellido: str
    identificacion: str
    origen: Optional[str] = None
    fuente_registro: Optional[str] = None
    datos_contextuales: Optional[dict] = None
    fecha_inscripcion: Optional[datetime] = None

class InscribirPacientesRequest(BaseModel):
    paciente_ids: List[int]


# ── Helpers ────────────────────────────────────────────────────────────

def generate_slug(nombre: str) -> str:
    """Genera un slug URL-friendly a partir del nombre."""
    slug = nombre.lower().strip()
    # Reemplazar caracteres acentuados
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u',
    }
    for char, replacement in replacements.items():
        slug = slug.replace(char, replacement)
    # Solo alfanuméricos y guiones
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("", response_model=CampanaResponse, status_code=status.HTTP_201_CREATED)
async def crear_campana(
    payload: CampanaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva campaña."""
    if payload.tipo not in ("secundaria", "servicio_externo", "campana_externa"):
        raise HTTPException(
            status_code=400,
            detail="Tipo de campaña inválido. Valores permitidos: secundaria, servicio_externo, campana_externa"
        )

    base_slug = generate_slug(payload.nombre)
    slug = base_slug

    # Asegurar unicidad del slug
    counter = 1
    while True:
        existing = await db.execute(select(Campana).where(Campana.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    campana = Campana(
        nombre=payload.nombre,
        slug=slug,
        tipo=payload.tipo,
        descripcion=payload.descripcion,
        fecha_inicio=payload.fecha_inicio,
        fecha_fin=payload.fecha_fin,
        ubicacion=payload.ubicacion,
        direccion=payload.direccion,
        estado=payload.estado or "activa",
    )
    db.add(campana)
    await db.commit()
    await db.refresh(campana)

    return CampanaResponse(
        id=campana.id,
        nombre=campana.nombre,
        slug=campana.slug,
        tipo=campana.tipo,
        descripcion=campana.descripcion,
        fecha_inicio=campana.fecha_inicio,
        fecha_fin=campana.fecha_fin,
        ubicacion=campana.ubicacion,
        direccion=campana.direccion,
        estado=campana.estado,
        total_pacientes=0,
        created_at=campana.created_at,
    )


@router.get("", response_model=List[CampanaResponse])
async def listar_campanas(
    tipo: Optional[str] = None,
    estado: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista campañas con filtros opcionales."""
    # Subquery para contar pacientes por campaña
    count_sub = (
        select(
            CampanaPaciente.campana_id,
            func.count(CampanaPaciente.id).label("total_pacientes")
        )
        .group_by(CampanaPaciente.campana_id)
        .subquery()
    )

    stmt = (
        select(Campana, func.coalesce(count_sub.c.total_pacientes, 0).label("total_pacientes"))
        .outerjoin(count_sub, Campana.id == count_sub.c.campana_id)
    )

    if tipo:
        stmt = stmt.where(Campana.tipo == tipo)
    if estado:
        stmt = stmt.where(Campana.estado == estado)

    stmt = stmt.order_by(desc(Campana.created_at)).offset((page - 1) * limit).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        CampanaResponse(
            id=c.id,
            nombre=c.nombre,
            slug=c.slug,
            tipo=c.tipo,
            descripcion=c.descripcion,
            fecha_inicio=c.fecha_inicio,
            fecha_fin=c.fecha_fin,
            ubicacion=c.ubicacion,
            direccion=c.direccion,
            estado=c.estado,
            total_pacientes=total,
            created_at=c.created_at,
        )
        for c, total in rows
    ]


@router.get("/stats/por-origen")
async def estadisticas_por_origen(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Devuelve conteos de pacientes agrupados por origen."""
    stmt = (
        select(Paciente.origen, func.count(Paciente.id))
        .group_by(Paciente.origen)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {"origen": origen or "sin_clasificar", "cantidad": cantidad}
        for origen, cantidad in rows
    ]

@router.get("/{campana_id}", response_model=CampanaResponse)
async def obtener_campana(
    campana_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene el detalle de una campaña."""
    stmt = select(Campana).where(Campana.id == campana_id)
    result = await db.execute(stmt)
    campana = result.scalar_one_or_none()

    if not campana:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    # Contar pacientes
    count_res = await db.execute(
        select(func.count(CampanaPaciente.id))
        .where(CampanaPaciente.campana_id == campana_id)
    )
    total = count_res.scalar() or 0

    return CampanaResponse(
        id=campana.id,
        nombre=campana.nombre,
        slug=campana.slug,
        tipo=campana.tipo,
        descripcion=campana.descripcion,
        fecha_inicio=campana.fecha_inicio,
        fecha_fin=campana.fecha_fin,
        ubicacion=campana.ubicacion,
        direccion=campana.direccion,
        estado=campana.estado,
        total_pacientes=total,
        created_at=campana.created_at,
    )


@router.patch("/{campana_id}", response_model=CampanaResponse)
async def actualizar_campana(
    campana_id: int,
    payload: CampanaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza una campaña existente."""
    stmt = select(Campana).where(Campana.id == campana_id)
    result = await db.execute(stmt)
    campana = result.scalar_one_or_none()

    if not campana:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    if payload.nombre is not None:
        campana.nombre = payload.nombre
    if payload.descripcion is not None:
        campana.descripcion = payload.descripcion
    if payload.fecha_inicio is not None:
        campana.fecha_inicio = payload.fecha_inicio
    if payload.fecha_fin is not None:
        campana.fecha_fin = payload.fecha_fin
    if payload.ubicacion is not None:
        campana.ubicacion = payload.ubicacion
    if payload.direccion is not None:
        campana.direccion = payload.direccion
    if payload.estado is not None:
        if payload.estado not in ("planificada", "activa", "cerrada"):
            raise HTTPException(status_code=400, detail="Estado inválido")
        campana.estado = payload.estado

    await db.commit()
    await db.refresh(campana)

    count_res = await db.execute(
        select(func.count(CampanaPaciente.id))
        .where(CampanaPaciente.campana_id == campana_id)
    )
    total = count_res.scalar() or 0

    return CampanaResponse(
        id=campana.id,
        nombre=campana.nombre,
        slug=campana.slug,
        tipo=campana.tipo,
        descripcion=campana.descripcion,
        fecha_inicio=campana.fecha_inicio,
        fecha_fin=campana.fecha_fin,
        ubicacion=campana.ubicacion,
        direccion=campana.direccion,
        estado=campana.estado,
        total_pacientes=total,
        created_at=campana.created_at,
    )


@router.get("/{campana_id}/pacientes", response_model=List[CampanaPacienteResponse])
async def listar_pacientes_campana(
    campana_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lista los pacientes inscritos en una campaña."""
    # Verificar que la campaña existe
    campana_res = await db.execute(select(Campana).where(Campana.id == campana_id))
    if not campana_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    stmt = (
        select(CampanaPaciente, Paciente)
        .join(Paciente, CampanaPaciente.paciente_id == Paciente.id)
        .where(CampanaPaciente.campana_id == campana_id)
        .order_by(Paciente.apellido, Paciente.nombre)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for cp, pac in rows:
        datos = None
        if cp.datos_contextuales:
            try:
                datos = json.loads(cp.datos_contextuales)
            except Exception:
                datos = {"raw": cp.datos_contextuales}

        items.append(CampanaPacienteResponse(
            id=cp.id,
            paciente_id=pac.id,
            nombre=pac.nombre,
            apellido=pac.apellido,
            identificacion=pac.identificacion,
            origen=pac.origen,
            fuente_registro=cp.fuente_registro,
            datos_contextuales=datos,
            fecha_inscripcion=cp.fecha_inscripcion,
        ))

    return items


@router.get("/{campana_id}/reportes-pdf")
async def exportar_pdfs_campana(
    campana_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Descarga un ZIP con los reportes PDF ya generados de los pacientes
    inscritos en la campaña (el más reciente de cada paciente).
    """
    campana_res = await db.execute(select(Campana).where(Campana.id == campana_id))
    campana = campana_res.scalar_one_or_none()
    if not campana:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    paciente_ids_res = await db.execute(
        select(CampanaPaciente.paciente_id).where(CampanaPaciente.campana_id == campana_id)
    )
    paciente_ids = [r[0] for r in paciente_ids_res.all()]
    if not paciente_ids:
        raise HTTPException(status_code=404, detail="La campaña no tiene pacientes inscritos")

    reportes_res = await db.execute(
        select(ReporteGenerado)
        .where(ReporteGenerado.paciente_id.in_(paciente_ids))
        .options(selectinload(ReporteGenerado.paciente))
        .order_by(ReporteGenerado.paciente_id, desc(ReporteGenerado.fecha_generacion))
    )
    reportes = reportes_res.scalars().all()

    # Quedarnos con un solo reporte por paciente (el mas reciente; la query ya viene ordenada)
    vistos = set()
    reportes_unicos = []
    for r in reportes:
        if r.paciente_id in vistos:
            continue
        vistos.add(r.paciente_id)
        reportes_unicos.append(r)

    if not reportes_unicos:
        raise HTTPException(
            status_code=404,
            detail="Ningún paciente de esta campaña tiene un reporte PDF generado todavía"
        )

    zip_buffer = io.BytesIO()
    incluidos = 0
    faltantes = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in reportes_unicos:
            if not r.ruta_archivo or not os.path.isfile(r.ruta_archivo):
                faltantes += 1
                continue
            pac = r.paciente
            apellido = (pac.apellido or "").strip().replace(" ", "_") if pac else ""
            nombre = (pac.nombre or "").strip().replace(" ", "_") if pac else ""
            nombre_archivo = f"{r.folio}_{apellido}_{nombre}.pdf".strip("_")
            zf.write(r.ruta_archivo, arcname=nombre_archivo)
            incluidos += 1

    if incluidos == 0:
        raise HTTPException(
            status_code=404,
            detail="Los reportes de esta campaña no tienen archivo PDF disponible en el servidor"
        )

    zip_buffer.seek(0)
    slug = campana.slug or f"campana-{campana.id}"
    filename = f"Reportes_{slug}_{date.today().isoformat()}.zip"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "X-Pacientes-Sin-Reporte, X-Pacientes-Incluidos",
        "X-Pacientes-Sin-Reporte": str(faltantes),
        "X-Pacientes-Incluidos": str(incluidos),
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


@router.post("/{campana_id}/pacientes")
async def inscribir_pacientes(
    campana_id: int,
    payload: InscribirPacientesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Inscribe pacientes existentes en una campaña."""
    campana_res = await db.execute(select(Campana).where(Campana.id == campana_id))
    campana = campana_res.scalar_one_or_none()
    if not campana:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")

    inscritos = 0
    duplicados = 0

    for pid in payload.paciente_ids:
        # Verificar que el paciente existe
        pac_res = await db.execute(select(Paciente).where(Paciente.id == pid))
        if not pac_res.scalar_one_or_none():
            continue

        # Verificar duplicado
        existing = await db.execute(
            select(CampanaPaciente).where(
                CampanaPaciente.campana_id == campana_id,
                CampanaPaciente.paciente_id == pid
            )
        )
        if existing.scalar_one_or_none():
            duplicados += 1
            continue

        cp = CampanaPaciente(
            campana_id=campana_id,
            paciente_id=pid,
            fuente_registro="manual",
        )
        db.add(cp)
        inscritos += 1

    await db.commit()

    return {
        "status": "ok",
        "inscritos": inscritos,
        "duplicados": duplicados,
        "mensaje": f"Se inscribieron {inscritos} paciente(s) en la campaña '{campana.nombre}'."
    }
