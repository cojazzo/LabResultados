import io
import json
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models import Lote, Prueba, User
from app.core.security import get_current_user
from app.services.excel_parser import process_excel_file, process_tamizaje_excel
from app.services.uc1000_parser import process_uc1000_csv
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


@router.post("/uc1000", response_model=UploadResponse)
async def upload_uc1000(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sube uno o varios archivos CSV del analizador de tiras reactivas UC-1000.
    Los valores de albúmina y creatinina de tira se cargan con fuente='tira_uc1000'.
    Si ya existe un valor de Vitros para la misma prueba/paciente/fecha, no se sobreescribe.
    El ACR se calcula automáticamente respetando la jerarquía Vitros > Tira.
    """
    lotes_procesados = []

    for file in files:
        # Aceptar .csv y opcionalmente .txt
        if not (file.filename.lower().endswith(".csv") or file.filename.lower().endswith(".txt")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo '{file.filename}' debe ser un CSV (.csv) del UC-1000."
            )

        file_content = await file.read()

        # Verificación rápida: primera línea debe contener 'UC-1000'
        try:
            first_line = file_content[:100].decode("utf-8", errors="replace")
            if "UC-1000" not in first_line:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El archivo '{file.filename}' no parece ser un CSV del UC-1000 "
                           "(no se encontró 'UC-1000' en la primera línea)."
                )
        except HTTPException:
            raise
        except Exception:
            pass  # Si no se puede leer, el parser reportará el error

        try:
            lote = await process_uc1000_csv(
                db=db,
                file_content=file_content,
                filename=file.filename,
                usuario_id=current_user.id
            )

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
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando el archivo UC-1000 '{file.filename}': {str(e)}"
            )

    return {
        "lotes": lotes_procesados,
        "mensaje": f"Se procesaron {len(lotes_procesados)} archivo(s) UC-1000 exitosamente."
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


@router.get("/template-excel")
async def descargar_template_excel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Descarga un archivo Excel template (.xlsx) con los encabezados correctos
    para que el laboratorio llene y suba los resultados.
    Formato horizontal: una fila por visita, con columnas de metadatos del paciente
    y una columna por cada prueba activa en el catálogo.
    """
    # Cargar pruebas activas del catálogo para generar las columnas dinámicas
    pruebas_res = await db.execute(
        select(Prueba).where(Prueba.activa == True).order_by(Prueba.nombre)
    )
    pruebas = pruebas_res.scalars().all()

    # Columnas fijas de metadatos (igual al formato horizontal que ya acepta el parser)
    meta_cols = [
        "Fecha",          # fecha de toma de muestra (requerido)
        "NTS",            # CURP del paciente (requerido)
        "Nombre del Paciente",
        "Apellidos",
        "Sexo del Paciente",
        "Fecha Nacimiento",
        "Numero",         # número de petición (opcional)
    ]

    # Columnas de pruebas: una por cada prueba activa (nombre en mayúsculas = código)
    prueba_cols = [p.codigo for p in pruebas] if pruebas else ["CRTS", "CRE01", "ALBOR", "ACR"]

    all_cols = meta_cols + prueba_cols

    # Crear DataFrame vacío con 3 filas de ejemplo comentadas (como guía)
    prueba_cols_ejemplo = {p.codigo: "" for p in pruebas} if pruebas else {"CRTS": "", "CRE01": "", "ALBOR": "", "ACR": ""}
    example_rows = [
        {
            "Fecha": "2024-01-15",
            "NTS": "CURP18 caracteres aqui",
            "Nombre del Paciente": "JUAN",
            "Apellidos": "PÉREZ GARCÍA",
            "Sexo del Paciente": "M",
            "Fecha Nacimiento": "1985-03-20",
            "Numero": "12345",
            **prueba_cols_ejemplo,
        }
    ]
    # Eliminar la fila de ejemplo para que el archivo llegue limpio
    df = pd.DataFrame(columns=all_cols)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados Lab")
        ws = writer.sheets["Resultados Lab"]
        # Ajustar anchos de columna
        for col_cells in ws.columns:
            header_val = str(col_cells[0].value) if col_cells[0].value else ""
            ws.column_dimensions[col_cells[0].column_letter].width = max(len(header_val) + 4, 12)
        # Congelar la primera fila de encabezados
        ws.freeze_panes = "A2"
    output.seek(0)

    from datetime import date as date_today
    hoy = date_today.today().isoformat()

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Template_Laboratorio_{hoy}.xlsx"'},
    )



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
