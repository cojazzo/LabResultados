import os
from datetime import datetime
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config import get_settings
from app.models import ReporteGenerado, Envio, User
from jinja2 import Template

settings = get_settings()

# Configuración de fastapi-mail
mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.MAIL_USE_CREDENTIALS
)


EMAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; }
        .header { background-color: #1e3a5f; color: white; padding: 15px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { padding: 20px; }
        .footer { font-size: 11px; color: #718096; text-align: center; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>{{ lab_name }}</h2>
        </div>
        <div class="content">
            <p>Estimado/a Paciente <strong>{{ paciente_nombre }}</strong>,</p>
            <p>Le informamos que sus resultados de laboratorio solicitados ya están disponibles y han sido validados.</p>
            <p>Adjunto a este correo electrónico encontrará su reporte oficial en formato PDF (Folio: <strong>{{ folio }}</strong>).</p>
            <p>Si tiene alguna duda respecto a estos resultados, le sugerimos consultarlo con su médico solicitante.</p>
            <br>
            <p>Atentamente,<br><strong>Equipo de {{ lab_name }}</strong></p>
        </div>
        <div class="footer">
            <p>Este correo electrónico fue generado de manera automática, por favor no responda directamente a él.</p>
            <p>{{ lab_address }} | Tel: {{ lab_phone }}</p>
        </div>
    </div>
</body>
</html>
"""

async def send_report_email(db: AsyncSession, reporte_id: int, destinatario_email: str, enviado_por: int) -> Envio:
    """
    Envía el PDF de un reporte por correo electrónico.
    Soporta modo Mock guardando el correo como archivo local.
    """
    # 1. Buscar el reporte con relación al paciente y sus resultados
    reporte_res = await db.execute(
        select(ReporteGenerado)
        .where(ReporteGenerado.id == reporte_id)
        .options(
            selectinload(ReporteGenerado.paciente),
            selectinload(ReporteGenerado.reporte_resultados)
        )
    )
    reporte = reporte_res.scalar_one_or_none()
    if not reporte:
        raise ValueError(f"Reporte con ID {reporte_id} no encontrado")

    paciente = reporte.paciente
    paciente_nombre = f"{paciente.nombre} {paciente.apellido}"

    if destinatario_email and paciente:
        if not paciente.email or paciente.email != destinatario_email:
            paciente.email = destinatario_email
            db.add(paciente)

    resultado_ids = [rr.resultado_id for rr in reporte.reporte_resultados] if reporte.reporte_resultados else [reporte.id]

    # 2. Registrar el envío en estado "pendiente"
    envio = Envio(
        reporte_id=reporte.id,
        canal="email",
        destinatario=destinatario_email,
        estado="pendiente",
        intentos=0,
        enviado_por=enviado_por
    )
    db.add(envio)
    await db.flush()

    import httpx

    # El cuerpo del correo lo puede construir n8n usando su nodo Email, pero le enviamos los datos crudos.
    pdf_url = f"{settings.BASE_URL}/storage/pdfs/{reporte.folio}.pdf"

    payload = {
        "resultado_ids": resultado_ids,
        "reporte_id": reporte.id,
        "folio": reporte.folio,
        "paciente_nombre": paciente_nombre,
        "destinatario": destinatario_email,
        "canal": "email",
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
