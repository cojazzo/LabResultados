import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models import Lote, User
from app.core.security import get_current_user
from app.services.excel_parser import process_excel_file, process_tamizaje_excel
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/upload", tags=["Carga de Excel"])

class LoteResponse(BaseModel):
    id: int
    nombre: str
    fecha_carga: datetime
    estado: str
    total_registros: int
    registros_exitosos: int
    registros_error: int
    log_errores: Optional[List] = None

    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    lotes: List[LoteResponse]
    mensaje: str

@router.post("/excel", response_model=UploadResponse)
async def upload_excel(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sube uno o varios archivos Excel (.xlsx) y procesa su contenido.
    """
    lotes_procesados = []
    
    for file in files:
        if not file.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo '{file.filename}' no es un archivo Excel válido (.xlsx o .xls)"
            )
            
        file_content = await file.read()
        try:
            lote = await process_excel_file(
                db=db,
                file_content=file_content,
                filename=file.filename,
                usuario_id=current_user.id
            )
            
            # Formatear el log_errores si existe
            log_err = None
            if lote.log_errores:
                try:
                    log_err = json.loads(lote.log_errores)
                except Exception:
                    log_err = [{"error": lote.log_errores}]
                    
            lotes_procesados.append(
                LoteResponse(
                    id=lote.id,
                    nombre=lote.nombre,
                    fecha_carga=lote.fecha_carga,
                    estado=lote.estado,
                    total_registros=lote.total_registros,
                    registros_exitosos=lote.registros_exitosos,
                    registros_error=lote.registros_error,
                    log_errores=log_err
                )
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo '{file.filename}': {str(e)}"
            )
            
    return {
        "lotes": lotes_procesados,
        "mensaje": f"Se procesaron {len(lotes_procesados)} archivo(s) exitosamente."
    }

@router.post("/tamizaje", response_model=UploadResponse)
async def upload_tamizaje(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sube uno o varios archivos Excel (.xlsx) de tamizaje (Google Forms) y procesa su contenido.
    """
    lotes_procesados = []
    
    for file in files:
        if not file.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo '{file.filename}' no es un archivo Excel válido (.xlsx o .xls)"
            )
            
        file_content = await file.read()
        try:
            resultado = await process_tamizaje_excel(
                db=db,
                file_content=file_content,
                filename=file.filename,
                usuario_id=current_user.id
            )
            lote = resultado["lote"]
            
            # Formatear el log_errores si existe
            log_err = None
            if lote.log_errores:
                try:
                    log_err = json.loads(lote.log_errores)
                except Exception:
                    log_err = [{"error": lote.log_errores}]
                    
            lotes_procesados.append(
                LoteResponse(
                    id=lote.id,
                    nombre=lote.nombre,
                    fecha_carga=lote.fecha_carga,
                    estado=lote.estado,
                    total_registros=lote.total_registros,
                    registros_exitosos=lote.registros_exitosos,
                    registros_error=lote.registros_error,
                    log_errores=log_err
                )
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo de tamizaje '{file.filename}': {str(e)}"
            )
            
    return {
        "lotes": lotes_procesados,
        "mensaje": f"Se procesaron {len(lotes_procesados)} archivo(s) de tamizaje exitosamente."
    }


@router.get("/lotes", response_model=List[LoteResponse])
async def get_lotes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene la lista de lotes de carga paginados.
    """
    offset = (page - 1) * limit
    stmt = (
        select(Lote)
        .order_by(desc(Lote.fecha_carga))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    lotes = result.scalars().all()
    
    # Formatear los registros para la respuesta
    response_items = []
    for l in lotes:
        log_err = None
        if l.log_errores:
            try:
                log_err = json.loads(l.log_errores)
            except Exception:
                log_err = [{"error": l.log_errores}]
                
        response_items.append(
            LoteResponse(
                id=l.id,
                nombre=l.nombre,
                fecha_carga=l.fecha_carga,
                estado=l.estado,
                total_registros=l.total_registros,
                registros_exitosos=l.registros_exitosos,
                registros_error=l.registros_error,
                log_errores=log_err
            )
        )
    return response_items

@router.get("/lotes/{lote_id}", response_model=LoteResponse)
async def get_lote(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el detalle de un lote de carga específico por su ID.
    """
    stmt = select(Lote).where(Lote.id == lote_id)
    result = await db.execute(stmt)
    lote = result.scalar_one_or_none()
    
    if not lote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lote de carga con ID {lote_id} no encontrado"
        )
        
    log_err = None
    if lote.log_errores:
        try:
            log_err = json.loads(lote.log_errores)
        except Exception:
            log_err = [{"error": lote.log_errores}]
            
    return LoteResponse(
        id=lote.id,
        nombre=lote.nombre,
        fecha_carga=lote.fecha_carga,
        estado=lote.estado,
        total_registros=lote.total_registros,
        registros_exitosos=lote.registros_exitosos,
        registros_error=lote.registros_error,
        log_errores=log_err
    )
