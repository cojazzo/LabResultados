import os
from datetime import datetime
from twilio.rest import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config import get_settings
from app.models import ReporteGenerado, Envio

settings = get_settings()

async def send_report_whatsapp(db: AsyncSession, reporte_id: int, destinatario_whatsapp: str, enviado_por: int) -> Envio:
    """
    Envía un mensaje de WhatsApp al paciente con el enlace del PDF de resultados.
    Soporta modo Mock guardando la bitácora de envío en un archivo local.
    """
    # 1. Buscar reporte
    reporte_res = await db.execute(
        select(ReporteGenerado)
        .where(ReporteGenerado.id == reporte_id)
        .options(selectinload(ReporteGenerado.paciente))
    )
    reporte = reporte_res.scalar_one_or_none()
    if not reporte:
        raise ValueError(f"Reporte con ID {reporte_id} no encontrado")

    paciente = reporte.paciente
    paciente_nombre = f"{paciente.nombre} {paciente.apellido}"

    # Normalizar número de teléfono (debe iniciar con whatsapp:+...)
    dest = destinatario_whatsapp.strip()
    if not dest.startswith("whatsapp:"):
        # Limpiar caracteres no numéricos excepto +
        clean_num = "".join(c for c in dest if c.isdigit() or c == '+')
        if not clean_num.startswith("+"):
            clean_num = f"+{clean_num}"  # Asumir código internacional
        dest = f"whatsapp:{clean_num}"

    # 2. Registrar envío
    envio = Envio(
        reporte_id=reporte.id,
        canal="whatsapp",
        destinatario=dest,
        estado="pendiente",
        intentos=0,
        enviado_por=enviado_por
    )
    db.add(envio)
    await db.flush()

    envio.intentos += 1

    import httpx

    # Construir cuerpo del mensaje (opcional, n8n puede armarlo también, pero lo enviamos por si acaso)
    mensaje_body = (
        f"Hola {paciente_nombre}. Sus resultados de laboratorio en *{settings.LAB_NAME}* "
        f"ya están listos. Folio: *{reporte.folio}*.\n"
        f"Puede descargar su reporte PDF oficial de manera segura aquí: "
        f"{settings.BASE_URL}/storage/pdfs/{reporte.folio}.pdf"
    )

    pdf_url = f"{settings.BASE_URL}/storage/pdfs/{reporte.folio}.pdf"

    payload = {
        "reporte_id": reporte.id,
        "folio": reporte.folio,
        "paciente_nombre": paciente_nombre,
        "destinatario": dest,
        "canal": "whatsapp",
        "mensaje": mensaje_body,
        "pdf_url": pdf_url
    }

    try:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {settings.N8N_WEBHOOK_SECRET}"}
            response = await client.post(settings.N8N_WEBHOOK_URL, json=payload, headers=headers)
            response.raise_for_status()

        envio.estado = "enviado"
        envio.fecha_envio = datetime.now()
        reporte.estado = "enviado"
        await db.commit()
        return envio

    except Exception as e:
        envio.estado = "fallido"
        envio.error_detalle = f"Error enviando webhook a n8n: {str(e)}"
        await db.commit()
        return envio
