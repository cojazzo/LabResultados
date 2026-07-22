#!/usr/bin/env python3
"""
EWS Email Server - Sistema de envío de emails para LabResultados
Utiliza Exchange Web Services del Gobierno de Aguascalientes
Soporta adjuntos en Base64.
"""

import os
import logging
import base64
from typing import Optional, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
import uvicorn

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Intentar importar exchangelib
try:
    from exchangelib import Account, Configuration, NTLM, Message, Mailbox, HTMLBody, FileAttachment
except ImportError as e:
    logger.error(f"exchangelib no instalado: {e}")
    logger.error("Instala con: pip3 install exchangelib --break-system-packages")

# Variables de entorno
EWS_USERNAME = os.getenv('EWS_USERNAME', 'gobags\\inaer.resultados')
EWS_PASSWORD = os.getenv('EWS_PASSWORD', '')
EWS_EMAIL = os.getenv('EWS_EMAIL', 'inaer.resultados@aguascalientes.gob.mx')
EWS_URL = os.getenv('EWS_URL', 'https://autodiscover.aguascalientes.gob.mx/EWS/Exchange.asmx')
API_KEY = os.getenv('EWS_API_KEY', 'change-me-in-production')

if not EWS_PASSWORD:
    logger.warning("⚠️  EWS_PASSWORD no configurada - verifica tu archivo .env o configuración del servicio")

# Modelos Pydantic
class Attachment(BaseModel):
    filename: str
    content_base64: str

class EmailRequest(BaseModel):
    """Modelo de solicitud para enviar email"""
    to: str  # Puede ser comma-separated
    subject: str
    body: str
    is_html: bool = False
    cc: Optional[str] = None
    bcc: Optional[str] = None
    attachments: Optional[List[Attachment]] = None

class EmailResponse(BaseModel):
    """Modelo de respuesta"""
    success: bool
    message: str
    to: List[str] = []
    subject: Optional[str] = None
    error: Optional[str] = None

# Crear aplicación FastAPI
app = FastAPI(
    title="EWS Email Service",
    description="Sistema de envío de emails para LabResultados via EWS (Soporte Base64)",
    version="1.1.0"
)

@app.get("/health")
async def health():
    """Verificar estado del servidor"""
    return {
        "status": "ok",
        "ews_configured": bool(EWS_PASSWORD),
        "ews_email": EWS_EMAIL,
        "version": "1.1.0"
    }

@app.post("/send-email", response_model=EmailResponse)
async def send_email(request: EmailRequest, x_api_key: Optional[str] = Header(None)):
    """
    Enviar email con adjuntos via EWS
    Requiere header X-API-Key con la API key correcta
    """
    
    if x_api_key != API_KEY:
        logger.warning(f"❌ Intento con API key inválida")
        raise HTTPException(status_code=401, detail="API key inválida")
    
    if not EWS_PASSWORD:
        return EmailResponse(
            success=False,
            message="Error: Servidor no configurado",
            error="EWS_PASSWORD no está configurada"
        )
    
    try:
        logger.info(f"📧 Enviando email a: {request.to}")
        
        config = Configuration(
            server=EWS_URL,
            credentials=(EWS_USERNAME, EWS_PASSWORD),
            auth_type=NTLM,
            verify_certificate=False
        )
        
        account = Account(
            primary_smtp_address=EWS_EMAIL,
            config=config,
            autodiscover=False,
            access_type='delegate'
        )
        
        # Probar conectividad
        _ = account.root
        logger.info("✓ Conectado a EWS")
        
        to_list = [addr.strip() for addr in request.to.split(",")]
        cc_list = [addr.strip() for addr in request.cc.split(",")] if request.cc else []
        bcc_list = [addr.strip() for addr in request.bcc.split(",")] if request.bcc else []
        
        msg = Message(
            account=account,
            subject=request.subject,
            body=request.body,
            to_recipients=[Mailbox(email_address=addr) for addr in to_list],
            cc_recipients=[Mailbox(email_address=addr) for addr in cc_list] if cc_list else [],
            bcc_recipients=[Mailbox(email_address=addr) for addr in bcc_list] if bcc_list else [],
        )
        
        if request.is_html:
            msg.body = HTMLBody(request.body)
        
        if request.attachments:
            for att in request.attachments:
                try:
                    content_bytes = base64.b64decode(att.content_base64)
                    attachment = FileAttachment(name=att.filename, content=content_bytes)
                    msg.attachments.add(attachment)
                    logger.info(f"📎 Adjunto agregado: {att.filename} ({len(content_bytes)/1024:.1f} KB)")
                except Exception as e:
                    logger.error(f"❌ Error decodificando adjunto {att.filename}: {e}")
                    continue
        
        msg.send()
        logger.info(f"✅ Email enviado correctamente a {to_list}")
        
        return EmailResponse(
            success=True,
            message="Email enviado exitosamente",
            to=to_list,
            subject=request.subject
        )
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error enviando email: {error_msg}")
        return EmailResponse(
            success=False,
            message="Error procesando solicitud",
            error=error_msg
        )

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Iniciando EWS Email Service para LabResultados")
    logger.info("=" * 60)
    logger.info(f"📧 Email: {EWS_EMAIL}")
    logger.info(f"🔗 URL EWS: {EWS_URL}")
    logger.info(f"👤 Usuario: {EWS_USERNAME}")
    logger.info(f"🔑 API Key configurada: {bool(API_KEY != 'change-me-in-production')}")
    logger.info("=" * 60)
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        log_level="info"
    )
