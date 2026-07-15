from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Envio, User, ReporteGenerado
from app.core.security import get_current_user
from app.services.email_sender import send_report_email
from app.services.whatsapp_sender import send_report_whatsapp
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

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
