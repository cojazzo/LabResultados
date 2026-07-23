from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Paciente
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

router = APIRouter(tags=["Pacientes y Cuestionarios"])

class CuestionarioClinicoInput(BaseModel):
    curp: str
    nombre: str
    apellido_paterno: str
    apellido_materno: Optional[str] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    edad: Optional[int] = None
    estado_origen: Optional[str] = None
    domicilio: Optional[str] = None
    codigo_postal: Optional[str] = None
    estado_residencia: Optional[str] = None
    municipio_residencia: Optional[str] = None
    peso: Optional[float] = None
    estatura: Optional[float] = None
    derechohabiencia: Optional[str] = None
    toma_suplemento: Optional[str] = None
    tipo_agua: Optional[str] = None
    cocina_agua_llave: Optional[str] = None
    padecimientos: Optional[List[str]] = None

class PacienteCuestionarioUpdate(BaseModel):
    identificacion: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    whatsapp: Optional[str] = None
    peso: Optional[float] = None
    estatura: Optional[float] = None
    tipo_agua: Optional[str] = None
    cocina_agua_llave: Optional[str] = None
    padecimientos: Optional[str] = None
    suplemento_detalle: Optional[str] = None

class PacienteDetalleResponse(BaseModel):
    id: int
    identificacion: str
    nombre: str
    apellido: str
    apellido_materno: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    domicilio: Optional[str] = None
    codigo_postal: Optional[str] = None
    estado_residencia: Optional[str] = None
    municipio_residencia: Optional[str] = None
    peso: Optional[float] = None
    estatura: Optional[float] = None
    derechohabiencia: Optional[str] = None
    suplemento_detalle: Optional[str] = None
    tipo_agua: Optional[str] = None
    cocina_agua_llave: Optional[str] = None
    padecimientos: Optional[str] = None

    class Config:
        from_attributes = True

@router.post("/pacientes/cuestionario", status_code=status.HTTP_200_OK)
async def recibir_cuestionario(payload: CuestionarioClinicoInput, db: AsyncSession = Depends(get_db)):
    """
    Recibe la información clínica del cuestionario de n8n.
    Realiza un upsert del paciente basado en su CURP (identificacion).
    """
    print(f"DEBUG INCOMING PAYLOAD: {payload.model_dump()}")
    curp_normalized = payload.curp.strip().upper()
    if not curp_normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La CURP es obligatoria para registrar el cuestionario."
        )

    # Buscar paciente existente
    stmt = select(Paciente).where(Paciente.identificacion == curp_normalized)
    result = await db.execute(stmt)
    paciente = result.scalar_one_or_none()

    # Combinar lista de padecimientos en un string separado por comas
    padecimientos_str = ",".join(payload.padecimientos) if payload.padecimientos else None

    # Mapear campos comunes
    sex_val = "F" if payload.sexo and payload.sexo.lower() in ["femenino", "f", "mujer"] else ("M" if payload.sexo and payload.sexo.lower() in ["masculino", "m", "hombre"] else None)

    if paciente:
        # Actualizar paciente existente
        paciente.nombre = payload.nombre.strip()
        paciente.apellido = payload.apellido_paterno.strip()
        paciente.apellido_materno = payload.apellido_materno.strip() if payload.apellido_materno else None
        if payload.fecha_nacimiento:
            paciente.fecha_nacimiento = payload.fecha_nacimiento
        if sex_val:
            paciente.sexo = sex_val
        if payload.telefono:
            paciente.telefono = payload.telefono.strip()
            paciente.whatsapp = payload.telefono.strip()
        if payload.email:
            paciente.email = payload.email.strip()
            
        paciente.domicilio = payload.domicilio
        paciente.codigo_postal = payload.codigo_postal
        paciente.estado_residencia = payload.estado_residencia
        paciente.municipio_residencia = payload.municipio_residencia
        paciente.peso = payload.peso
        paciente.estatura = payload.estatura
        paciente.derechohabiencia = payload.derechohabiencia
        paciente.suplemento_detalle = payload.toma_suplemento
        paciente.tipo_agua = payload.tipo_agua
        paciente.cocina_agua_llave = payload.cocina_agua_llave
        paciente.padecimientos = padecimientos_str
    else:
        # Crear nuevo paciente
        paciente = Paciente(
            identificacion=curp_normalized,
            nombre=payload.nombre.strip(),
            apellido=payload.apellido_paterno.strip(),
            apellido_materno=payload.apellido_materno.strip() if payload.apellido_materno else None,
            fecha_nacimiento=payload.fecha_nacimiento,
            sexo=sex_val,
            telefono=payload.telefono.strip() if payload.telefono else None,
            whatsapp=payload.telefono.strip() if payload.telefono else None,
            email=payload.email.strip() if payload.email else None,
            domicilio=payload.domicilio,
            codigo_postal=payload.codigo_postal,
            estado_residencia=payload.estado_residencia,
            municipio_residencia=payload.municipio_residencia,
            peso=payload.peso,
            estatura=payload.estatura,
            derechohabiencia=payload.derechohabiencia,
            suplemento_detalle=payload.toma_suplemento,
            tipo_agua=payload.tipo_agua,
            cocina_agua_llave=payload.cocina_agua_llave,
            padecimientos=padecimientos_str
        )
        db.add(paciente)

    await db.commit()
    await db.refresh(paciente)
    
    return {
        "status": "success",
        "message": "Cuestionario procesado correctamente.",
        "paciente_id": paciente.id,
        "identificacion": paciente.identificacion
    }

@router.get("/pacientes/{id}", response_model=PacienteDetalleResponse)
async def obtener_paciente(id: int, db: AsyncSession = Depends(get_db)):
    """
    Obtiene el perfil clínico detallado del paciente.
    """
    stmt = select(Paciente).where(Paciente.id == id)
    result = await db.execute(stmt)
    paciente = result.scalar_one_or_none()
    if not paciente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente con ID {id} no encontrado"
        )
    return paciente

@router.patch("/pacientes/{id}/cuestionario", response_model=PacienteDetalleResponse)
async def actualizar_cuestionario(id: int, payload: PacienteCuestionarioUpdate, db: AsyncSession = Depends(get_db)):
    """
    Actualiza manualmente los datos del cuestionario clínico de un paciente.
    """
    stmt = select(Paciente).where(Paciente.id == id)
    result = await db.execute(stmt)
    paciente = result.scalar_one_or_none()
    
    if not paciente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente con ID {id} no encontrado"
        )
        
    if payload.identificacion is not None:
        paciente.identificacion = payload.identificacion.strip().upper()
    if payload.email is not None:
        paciente.email = payload.email.strip() if payload.email.strip() else None
    if payload.telefono is not None:
        paciente.telefono = payload.telefono.strip() if payload.telefono.strip() else None
    if payload.whatsapp is not None:
        paciente.whatsapp = payload.whatsapp.strip() if payload.whatsapp.strip() else None
        
    if payload.peso is not None:
        paciente.peso = payload.peso
    if payload.estatura is not None:
        paciente.estatura = payload.estatura
    if payload.tipo_agua is not None:
        paciente.tipo_agua = payload.tipo_agua
    if payload.cocina_agua_llave is not None:
        paciente.cocina_agua_llave = payload.cocina_agua_llave
    if payload.padecimientos is not None:
        paciente.padecimientos = payload.padecimientos
    if payload.suplemento_detalle is not None:
        paciente.suplemento_detalle = payload.suplemento_detalle
        
    await db.commit()
    await db.refresh(paciente)
    
    return paciente
print("HOLA ESTOY AQUI")
