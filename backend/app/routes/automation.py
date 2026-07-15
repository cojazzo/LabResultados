from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional, List
import json
import pandas as pd
import io
import os
import base64
import httpx
from datetime import datetime

from app.database import get_db
from app.models import Paciente, AutomationEvent, User, ReporteGenerado
from app.config import get_settings
from app.utils.curp_validator import match_patient_identifier
from app.core.security import get_current_user
from app.utils.validators import normalize_column_name

router = APIRouter(tags=["automation"])

@router.post("/automation/questionnaires", status_code=status.HTTP_200_OK)
async def receive_google_forms_questionnaire(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook para recibir datos de Google Forms (vía n8n).
    Asegura idempotencia usando un event_id proporcionado en el payload.
    """
    event_id = payload.get("eventId")
    if not event_id:
        raise HTTPException(status_code=400, detail="eventId is required")
        
    # Idempotency check
    stmt = select(AutomationEvent).where(AutomationEvent.event_id == event_id)
    result = await db.execute(stmt)
    existing_event = result.scalar_one_or_none()
    
    if existing_event and existing_event.status == "processed":
        return {"status": "ok", "message": "Already processed", "patient_id": existing_event.entity_id}

    if not existing_event:
        existing_event = AutomationEvent(
            event_id=event_id,
            event_type="patient.questionnaire.submitted",
            status="pending"
        )
        db.add(existing_event)
        await db.commit()
        await db.refresh(existing_event)

    try:
        data = payload.get("data", {})
        nombre = data.get("nombre", "")
        apellido = data.get("apellido", "")
        curp_raw = data.get("curp")
        
        # Identificador principal
        identificador = match_patient_identifier(
            curp_raw, 
            nombre, 
            apellido,
            data.get("sexo"),
            # NOTA: En un caso real parsearíamos la fecha de nacimiento aquí
            None 
        )
        
        # Buscar paciente
        stmt = select(Paciente).where(Paciente.identificacion == identificador)
        result = await db.execute(stmt)
        paciente = result.scalar_one_or_none()
        
        if not paciente:
            paciente = Paciente(
                identificacion=identificador,
                nombre=nombre,
                apellido=apellido,
                email=data.get("email"),
                whatsapp=data.get("whatsapp")
            )
            db.add(paciente)
        else:
            # Actualizar datos si existen
            if data.get("email"): paciente.email = data.get("email")
            if data.get("whatsapp"): paciente.whatsapp = data.get("whatsapp")
            
        paciente.questionnaire_data = json.dumps(data)
        paciente.questionnaire_source_id = event_id
        
        # Consentimientos
        consents = data.get("consents", {})
        paciente.email_consent = consents.get("email", False)
        paciente.whatsapp_consent = consents.get("whatsapp", False)
        paciente.result_delivery_consent = consents.get("delivery", False)
        
        await db.commit()
        await db.refresh(paciente)
        
        existing_event.status = "processed"
        existing_event.entity_id = str(paciente.id)
        existing_event.processed_at = datetime.utcnow()
        await db.commit()
        
        return {"status": "ok", "patient_id": paciente.id, "identificador": identificador}
        
    except Exception as e:
        existing_event.status = "error"
        existing_event.sanitized_error = str(e)
        existing_event.attempt_count += 1
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/automation/reports/{reporte_id}/authorize")
async def authorize_report(
    reporte_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Autoriza un reporte generado para que pueda ser enviado por n8n.
    """
    stmt = select(ReporteGenerado).where(ReporteGenerado.id == reporte_id)
    result = await db.execute(stmt)
    reporte = result.scalar_one_or_none()
    
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
        
    reporte.authorized_by = current_user.id
    reporte.authorized_at = datetime.utcnow()
    reporte.estado = "autorizado"
    
    # 1. Leer el archivo PDF y codificar en base64
    pdf_base64 = None
    try:
        if os.path.exists(reporte.ruta_archivo):
            with open(reporte.ruta_archivo, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"Error leyendo PDF: {e}")

    # 2. Enviar a n8n (LAB-04)
    # Por defecto, la URL del webhook de n8n para este flujo. Se asume configurado en variables de entorno.
    settings = get_settings()
    n8n_url = os.getenv("N8N_WEBHOOK_LAB04_URL", "http://localhost:5678/webhook/lab-04-autorizado")
    
    payload = {
        "reporte_id": reporte.id,
        "paciente_id": reporte.paciente_id,
        "folio": reporte.folio,
        "pdf_base64": pdf_base64,
        "pdf_filename": os.path.basename(reporte.ruta_archivo)
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(n8n_url, json=payload, timeout=10.0)
    except Exception as e:
        print(f"Error enviando webhook a n8n: {e}")
    
    await db.commit()
    return {"status": "ok", "message": "Reporte autorizado correctamente"}

@router.post("/automation/lab-imports/preview")
async def preview_lab_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Previsualiza un Excel antes de cargarlo, indicando qué filas no hacen match con pacientes existentes.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel")
        
    file_content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(file_content), keep_default_na=False)
        df = df.replace("", None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {str(e)}")

    cols = {normalize_column_name(col): col for col in df.columns}
    
    # Intentar identificar la columna CURP o NTS
    curp_col = None
    for name in ["nts", "curp", "identificacion", "identificacion_paciente"]:
        if name in cols:
            curp_col = cols[name]
            break
            
    if not curp_col:
        return {"status": "error", "message": "No se encontró columna de identificación (NTS/CURP)"}

    # Buscar nombres para el ID sintético
    nombre_col = cols.get("nombre") or cols.get("nombre_del_paciente") or cols.get("nombre_paciente")
    apellido_col = cols.get("apellidos") or cols.get("apellido_paciente") or cols.get("apellido")

    rows_preview = []
    
    for index, row in df.iterrows():
        fila_num = index + 2
        identificador_raw = str(row[curp_col]).strip() if pd.notna(row[curp_col]) else ""
        nombre_raw = str(row[nombre_col]).strip() if nombre_col and pd.notna(row[nombre_col]) else ""
        apellido_raw = str(row[apellido_col]).strip() if apellido_col and pd.notna(row[apellido_col]) else ""
        
        # Omitir filas vacías
        if not identificador_raw and not nombre_raw and not apellido_raw:
            continue
            
        identificador = match_patient_identifier(
            identificador_raw,
            nombre_raw,
            apellido_raw
        )
        
        stmt = select(Paciente).where(Paciente.identificacion == identificador)
        res = await db.execute(stmt)
        paciente = res.scalar_one_or_none()
        
        rows_preview.append({
            "fila": fila_num,
            "identificador_original": identificador_raw,
            "identificador_usado": identificador,
            "nombre": nombre_raw,
            "apellido": apellido_raw,
            "match": paciente is not None,
            "paciente_id": paciente.id if paciente else None
        })
        
    return {
        "status": "ok",
        "total": len(rows_preview),
        "matches": sum(1 for r in rows_preview if r["match"]),
        "no_matches": sum(1 for r in rows_preview if not r["match"]),
        "rows": rows_preview
    }
