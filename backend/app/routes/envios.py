from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Envio, User, ReporteGenerado
from app.core.security import get_current_user, get_current_user_or_system
from app.services.email_sender import send_report_email
from app.services.whatsapp_sender import send_report_whatsapp
from datetime import datetime, timedelta
import os
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any
from datetime import datetime
import json
import httpx
from app.config import get_settings
router = APIRouter(prefix="/envios", tags=["Envíos"])

# Request/Response Pydantic models
class EnvioEmailRequest(BaseModel):
    reporte_id: int
    destinatario_email: EmailStr

class EnvioWhatsAppRequest(BaseModel):
    reporte_id: int
    destinatario_whatsapp: str

class EnvioResponse(BaseModel):
    id: int
    reporte_folio: str
    canal: str
    destinatario: str
    estado: str
    intentos: int
    error_detalle: Optional[str] = None
    fecha_envio: Optional[datetime] = None

    class Config:
        from_attributes = True

class EnvioPrepararRequest(BaseModel):
    resultado_ids: List[int]

class EnvioPreparadoResponse(BaseModel):
    id_envio: int
    folio: str
    nombre_destinatario: str
    email: str
    pdf_filename: str

class EnvioConfirmarRequest(BaseModel):
    id: str
    estado: str
    destinatario: Optional[str] = None
    asunto: Optional[str] = None
    error: Optional[str] = None
    fecha: Optional[str] = None

# --- Helper task for background sending ---
async def send_email_background(db_factory, r_id, email, user_id):
    async with db_factory() as db:
        await send_report_email(db, r_id, email, user_id)

async def send_whatsapp_background(db_factory, r_id, phone, user_id):
    async with db_factory() as db:
        await send_report_whatsapp(db, r_id, phone, user_id)

# --- Endpoints ---

@router.post("/email", response_model=EnvioResponse)
async def enviar_email(
    req: EnvioEmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Envía un reporte PDF por correo electrónico de forma asíncrona.
    """
    # Validar que existe el reporte
    stmt = select(ReporteGenerado).where(ReporteGenerado.id == req.reporte_id)
    result = await db.execute(stmt)
    reporte = result.scalar_one_or_none()
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte con ID {req.reporte_id} no encontrado"
        )

    # Creamos un Envio en estado pendiente para retornar de inmediato
    envio = Envio(
        reporte_id=reporte.id,
        canal="email",
        destinatario=req.destinatario_email,
        estado="pendiente",
        intentos=0,
        enviado_por=current_user.id
    )
    db.add(envio)
    await db.commit()
    await db.refresh(envio)

    # Lanzamos el proceso en segundo plano para no bloquear
    from app.database import AsyncSessionLocal
    background_tasks.add_task(
        send_email_background,
        AsyncSessionLocal,
        req.reporte_id,
        req.destinatario_email,
        current_user.id
    )

    return EnvioResponse(
        id=envio.id,
        reporte_folio=reporte.folio,
        canal=envio.canal,
        destinatario=envio.destinatario,
        estado=envio.estado,
        intentos=envio.intentos,
        fecha_envio=envio.fecha_envio
    )

@router.post("/whatsapp", response_model=EnvioResponse)
async def enviar_whatsapp(
    req: EnvioWhatsAppRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Envía un reporte PDF por WhatsApp de forma asíncrona.
    """
    # Validar que existe el reporte
    stmt = select(ReporteGenerado).where(ReporteGenerado.id == req.reporte_id)
    result = await db.execute(stmt)
    reporte = result.scalar_one_or_none()
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte con ID {req.reporte_id} no encontrado"
        )

    # Creamos un Envio en estado pendiente para retornar de inmediato
    envio = Envio(
        reporte_id=reporte.id,
        canal="whatsapp",
        destinatario=req.destinatario_whatsapp,
        estado="pendiente",
        intentos=0,
        enviado_por=current_user.id
    )
    db.add(envio)
    await db.commit()
    await db.refresh(envio)

    # Lanzamos el proceso en segundo plano
    from app.database import AsyncSessionLocal
    background_tasks.add_task(
        send_whatsapp_background,
        AsyncSessionLocal,
        req.reporte_id,
        req.destinatario_whatsapp,
        current_user.id
    )

    return EnvioResponse(
        id=envio.id,
        reporte_folio=reporte.folio,
        canal=envio.canal,
        destinatario=envio.destinatario,
        estado=envio.estado,
        intentos=envio.intentos,
        fecha_envio=envio.fecha_envio
    )

@router.get("", response_model=List[EnvioResponse])
async def get_envios(
    canal: Optional[str] = None,
    estado: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene la lista de envíos filtrada y paginada.
    """
    offset = (page - 1) * limit
    conditions = []
    
    if canal and canal != "todos":
        conditions.append(Envio.canal == canal)
    if estado and estado != "todos":
        conditions.append(Envio.estado == estado)

    stmt = (
        select(Envio)
        .where(and_(*conditions))
        .options(selectinload(Envio.reporte))
        .order_by(desc(Envio.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    envios = result.scalars().all()
    
    response_list = []
    for e in envios:
        response_list.append(
            EnvioResponse(
                id=e.id,
                reporte_folio=e.reporte.folio if e.reporte else "N/A",
                canal=e.canal,
                destinatario=e.destinatario,
                estado=e.estado,
                intentos=e.intentos,
                error_detalle=e.error_detalle,
                fecha_envio=e.fecha_envio
            )
        )
    return response_list

@router.post("/{id}/reintentar", response_model=EnvioResponse)
async def reintentar_envio_route(
    id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reintenta un envío fallido.
    """
    stmt = select(Envio).where(Envio.id == id).options(selectinload(Envio.reporte))
    result = await db.execute(stmt)
    envio = result.scalar_one_or_none()
    
    if not envio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Envío con ID {id} no encontrado"
        )
        
    # Cambiar estado a pendiente
    envio.estado = "pendiente"
    await db.commit()

    from app.database import AsyncSessionLocal
    if envio.canal == "email":
        background_tasks.add_task(
            send_email_background,
            AsyncSessionLocal,
            envio.reporte_id,
            envio.destinatario,
            current_user.id
        )
    elif envio.canal == "whatsapp":
        background_tasks.add_task(
            send_whatsapp_background,
            AsyncSessionLocal,
            envio.reporte_id,
            envio.destinatario,
            current_user.id
        )
        
    return EnvioResponse(
        id=envio.id,
        reporte_folio=envio.reporte.folio if envio.reporte else "N/A",
        canal=envio.canal,
        destinatario=envio.destinatario,
        estado=envio.estado,
        intentos=envio.intentos,
        fecha_envio=envio.fecha_envio
    )

@router.post("/preparar", response_model=List[EnvioPreparadoResponse])
async def preparar_envios(
    req: EnvioPrepararRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user_or_system)
):
    """
    Prepara los envíos para el puente de Outlook (n8n).
    Recibe IDs de resultado y genera una lista de tareas.
    """
    from app.models import ReporteResultado, ReporteGenerado, Paciente

    # Obtener los ReporteGenerado asociados a los resultado_ids
    stmt = (
        select(ReporteGenerado)
        .join(ReporteResultado, ReporteResultado.reporte_id == ReporteGenerado.id)
        .join(Paciente, Paciente.id == ReporteGenerado.paciente_id)
        .where(ReporteResultado.resultado_id.in_(req.resultado_ids))
        .options(selectinload(ReporteGenerado.paciente))
    )
    result = await db.execute(stmt)
    reportes = result.scalars().unique().all()
    
    if not reportes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron reportes generados para los resultados proporcionados."
        )

    response_list = []
    
    for reporte in reportes:
        paciente = reporte.paciente
        # Crear un Envio en estado preparado
        envio = Envio(
            reporte_id=reporte.id,
            canal="puente_outlook",
            destinatario=paciente.email if paciente.email else "sin-email@lab.com",
            estado="preparado_puente",
            intentos=0,
            enviado_por=current_user.id if hasattr(current_user, 'id') else None
        )
        db.add(envio)
        await db.commit()
        await db.refresh(envio)
        
        pdf_filename = os.path.basename(reporte.ruta_archivo) if reporte.ruta_archivo else f"{reporte.folio}.pdf"
        nombre_dest = f"{paciente.nombre} {paciente.apellido}".strip()
        
        response_list.append(
            EnvioPreparadoResponse(
                id_envio=envio.id,
                folio=reporte.folio,
                nombre_destinatario=nombre_dest,
                email=envio.destinatario,
                pdf_filename=pdf_filename
            )
        )
        
    return response_list

@router.post("/confirmar")
async def confirmar_envio(
    req: EnvioConfirmarRequest,
    db: AsyncSession = Depends(get_db),
    # Note: Authentication could be bypassed or checked depending on n8n setup
    current_user: Any = Depends(get_current_user_or_system)
):
    """
    Recibe la confirmación del puente de Outlook (vía n8n).
    """
    # Parse the ID. El ID viene como "folio_..." o simplemente se le puede haber 
    # enviado el id_envio en algún campo. Según la instrucción, el bridge envía
    # un id. Si es 'id_envio' puro o 'folio_algo'. 
    # Vamos a asumir que podemos buscarlo por su ID o Folio.
    import re
    # Intentar extraer el folio o id_envio
    
    # Primero vemos si "id" empieza con un folio que conocemos.
    # O mejor, en la arquitectura de n8n, si pasamos el id_envio, a lo mejor el puente nos lo devuelve.
    # Por ahora buscamos el Envio que esté en estado "preparado_puente" que corresponda.
    
    # Extract just the first part if it's separated by underscore
    folio_or_id = req.id.split("_")[0]
    
    # Buscar el envío
    stmt = (
        select(Envio)
        .join(ReporteGenerado, ReporteGenerado.id == Envio.reporte_id)
        .where(
            and_(
                (ReporteGenerado.folio == folio_or_id) | (Envio.id.cast(String) == folio_or_id),
                Envio.canal == "puente_outlook"
            )
        )
        .order_by(desc(Envio.created_at))
        .limit(1)
    )
    
    result = await db.execute(stmt)
    envio = result.scalar_one_or_none()
    
    if not envio:
        # Podría ser útil registrar esto de alguna forma, pero HTTP 404 es correcto
        raise HTTPException(status_code=404, detail="Envío original no encontrado")
        
    # Actualizar estado
    if req.estado == "enviado":
        envio.estado = "enviado"
        envio.fecha_envio = func.now()
    else:
        envio.estado = "fallido"
        envio.error_detalle = req.error or "Error desconocido del puente"
        
    await db.commit()
    return {"status": "ok", "envio_id": envio.id, "nuevo_estado": envio.estado}

@router.post("/outlook/trigger")
async def trigger_outlook_envio(
    req: EnvioPrepararRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Desencadena el webhook de n8n para el puente de Outlook usando X-Auth-Token.
    """
    settings = get_settings()
    
    # 1. Asegurar que haya Envíos preparados llamando a preparar_envios internamente o confiando 
    #    en que la app frontend mande los resultado_ids correctos. 
    #    Para simplificar, enviamos los IDs directamente a n8n.
    
    payload = {"resultado_ids": req.resultado_ids}
    headers = {"X-Auth-Token": settings.N8N_OUTLOOK_WEBHOOK_SECRET}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.N8N_OUTLOOK_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enviando solicitud a n8n: {str(e)}"
        )
        
    return {"status": "ok", "message": "Enviado exitosamente a n8n para Outlook"}
