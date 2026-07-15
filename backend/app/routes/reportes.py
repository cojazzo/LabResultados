import os
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import ReporteGenerado, User, Paciente
from app.core.security import get_current_user
from app.services.pdf_generator import generate_report_pdf, generate_batch_reports
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/reportes", tags=["Reportes PDF"])

class GenerarReporteRequest(BaseModel):
    paciente_id: int
    resultado_ids: List[int]
    lote_id: Optional[int] = None
    quimico_id: Optional[int] = None

class GenerarMasivoRequest(BaseModel):
    lote_id: int
    quimico_id: Optional[int] = None

class ReporteResponse(BaseModel):
    id: int
    folio: str
    paciente_nombre: str
    paciente_id: int
    fecha_generacion: datetime
    estado: str
    ruta_archivo: str

    class Config:
        from_attributes = True

@router.post("/generar", response_model=ReporteResponse)
async def generar_reporte(
    req: GenerarReporteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Genera un reporte PDF para un paciente con un conjunto específico de resultados.
    """
    try:
        reporte = await generate_report_pdf(
            db=db,
            paciente_id=req.paciente_id,
            resultado_ids=req.resultado_ids,
            generado_por=current_user.id,
            lote_id=req.lote_id,
            quimico_id=req.quimico_id
        )
        
        # Recargar para traer datos del paciente
        stmt = select(ReporteGenerado).where(ReporteGenerado.id == reporte.id).options(selectinload(ReporteGenerado.paciente))
        res = await db.execute(stmt)
        rep_full = res.scalar_one_or_none()
        
        pac_nombre = f"{rep_full.paciente.nombre} {rep_full.paciente.apellido}" if rep_full.paciente else "Desconocido"
        
        return ReporteResponse(
            id=rep_full.id,
            folio=rep_full.folio,
            paciente_nombre=pac_nombre,
            paciente_id=rep_full.paciente_id,
            fecha_generacion=rep_full.fecha_generacion,
            estado=rep_full.estado,
            ruta_archivo=rep_full.ruta_archivo
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando PDF: {str(e)}. TRACEBACK: {error_details}"
        )

@router.post("/generar-masivo", response_model=List[ReporteResponse])
async def generar_reporte_masivo(
    req: GenerarMasivoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Genera reportes PDF para todo un lote de resultados agrupado por paciente.
    """
    try:
        reportes = await generate_batch_reports(
            db=db,
            lote_id=req.lote_id,
            generado_por=current_user.id,
            quimico_id=req.quimico_id
        )
        
        response_list = []
        for r in reportes:
            # Traer datos del paciente
            stmt = select(ReporteGenerado).where(ReporteGenerado.id == r.id).options(selectinload(ReporteGenerado.paciente))
            res = await db.execute(stmt)
            rep_full = res.scalar_one_or_none()
            
            pac_nombre = f"{rep_full.paciente.nombre} {rep_full.paciente.apellido}" if rep_full.paciente else "Desconocido"
            
            response_list.append(
                ReporteResponse(
                    id=rep_full.id,
                    folio=rep_full.folio,
                    paciente_nombre=pac_nombre,
                    paciente_id=rep_full.paciente_id,
                    fecha_generacion=rep_full.fecha_generacion,
                    estado=rep_full.estado,
                    ruta_archivo=rep_full.ruta_archivo
                )
            )
        return response_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en generación masiva: {str(e)}"
        )

@router.get("", response_model=List[ReporteResponse])
async def get_reportes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los reportes PDF generados con paginación.
    """
    offset = (page - 1) * limit
    stmt = (
        select(ReporteGenerado)
        .options(selectinload(ReporteGenerado.paciente))
        .order_by(desc(ReporteGenerado.fecha_generacion))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    reportes = result.scalars().all()
    
    response_list = []
    for r in reportes:
        pac_nombre = f"{r.paciente.nombre} {r.paciente.apellido}" if r.paciente else "Desconocido"
        response_list.append(
            ReporteResponse(
                id=r.id,
                folio=r.folio,
                paciente_nombre=pac_nombre,
                paciente_id=r.paciente_id,
                fecha_generacion=r.fecha_generacion,
                estado=r.estado,
                ruta_archivo=r.ruta_archivo
            )
        )
    return response_list

@router.get("/{id}/descargar")
async def descargar_reporte(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Descarga el archivo PDF de un reporte específico.
    """
    stmt = select(ReporteGenerado).where(ReporteGenerado.id == id)
    result = await db.execute(stmt)
    reporte = result.scalar_one_or_none()
    
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte con ID {id} no encontrado"
        )
        
    if not os.path.exists(reporte.ruta_archivo):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo PDF físico no se encuentra en el servidor"
        )
        
    return FileResponse(
        path=reporte.ruta_archivo,
        media_type="application/pdf",
        filename=f"{reporte.folio}.pdf"
    )

class ReporteBusquedaResponse(BaseModel):
    folio: str
    paciente_nombre: str
    pdf_url: str

@router.get("/buscar-por-telefono", response_model=ReporteBusquedaResponse)
async def buscar_por_telefono(
    telefono: str = Query(..., description="Número de teléfono del paciente"),
    db: AsyncSession = Depends(get_db)
):
    """
    Busca el reporte más reciente de un paciente dado su número de teléfono.
    Este endpoint es de uso interno/webhook para automatizaciones (ej. n8n).
    """
    from app.config import get_settings
    settings = get_settings()

    # Limpiar el teléfono para dejar solo los últimos 10 dígitos (local)
    clean_phone = "".join(c for c in telefono if c.isdigit())
    if len(clean_phone) > 10:
        clean_phone = clean_phone[-10:]

    # Buscar al paciente por teléfono (que contenga los últimos 10 dígitos)
    stmt_pac = select(Paciente).where(Paciente.telefono.like(f"%{clean_phone}%"))
    res_pac = await db.execute(stmt_pac)
    paciente = res_pac.scalar_one_or_none()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado con ese teléfono")

    # Buscar el reporte más reciente del paciente (y que esté autorizado)
    stmt_rep = (
        select(ReporteGenerado)
        .where(ReporteGenerado.paciente_id == paciente.id)
        # .where(ReporteGenerado.authorized_at.isnot(None)) # Opcional: solo reportes autorizados
        .order_by(desc(ReporteGenerado.fecha_generacion))
        .limit(1)
    )
    res_rep = await db.execute(stmt_rep)
    reporte = res_rep.scalar_one_or_none()

    if not reporte:
        raise HTTPException(status_code=404, detail="El paciente no tiene reportes generados")

    pac_nombre = f"{paciente.nombre} {paciente.apellido}"
    pdf_url = f"{settings.BASE_URL}/storage/pdfs/{reporte.folio}.pdf"

    return ReporteBusquedaResponse(
        folio=reporte.folio,
        paciente_nombre=pac_nombre,
        pdf_url=pdf_url
    )
