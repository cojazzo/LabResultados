"""Alta manual de un paciente (datos personales + preguntas del cuestionario). Requiere sesión."""
import re
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models import Campana, CampanaPaciente, User
from app.services.identidad import ResolvedorIdentidad, curp_valida
from app.services.peticiones import normalizar_peticion, vincular_peticion
from app.services.registro_paciente import aplicar_datos
from app.utils.validators import normalizar_estatura_cm, normalizar_peso_kg, validate_email

router = APIRouter(tags=["Alta de pacientes"])


class ConsentimientosInput(BaseModel):
    email: bool = False
    whatsapp: bool = False
    entrega_resultados: bool = False


class PacienteAltaInput(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    apellido_paterno: str = Field(min_length=1, max_length=120)
    apellido_materno: Optional[str] = Field(default=None, max_length=120)
    sexo: str = Field(description="M/F (también Masculino/Femenino)")
    fecha_nacimiento: date
    curp: Optional[str] = Field(default=None, max_length=30)
    telefono: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=160)
    domicilio: Optional[str] = Field(default=None, max_length=250)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    estado_residencia: Optional[str] = Field(default=None, max_length=80)
    municipio_residencia: Optional[str] = Field(default=None, max_length=80)
    peso: Optional[float] = Field(default=None, description="kg")
    estatura: Optional[float] = Field(default=None, description="cm (si viene menor a 3 se toma como metros)")
    derechohabiencia: Optional[str] = Field(default=None, max_length=80)
    suplemento: Optional[str] = Field(default=None, max_length=200)
    tipo_agua: Optional[str] = Field(default=None, max_length=120)
    cocina_agua_llave: Optional[str] = Field(default=None, max_length=20)
    padecimientos: Optional[List[str]] = Field(default=None, max_length=30)
    consentimientos: ConsentimientosInput = Field(default_factory=ConsentimientosInput)
    id_peticion: Optional[str] = Field(default=None, description="ID de petición del servicio externo (8 dígitos)")
    campana_id: Optional[int] = Field(default=None, description="Inscribir en esta campaña")
    confirmar_actualizacion: bool = Field(
        default=False, description="Confirma que, si la persona ya existe, se actualicen sus datos con estos")


def _invalido(campo: str, mensaje: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{campo}: {mensaje}")


@router.post("/pacientes")
async def alta_paciente(
    payload: PacienteAltaInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Da de alta a un paciente con sus datos personales y las preguntas del cuestionario. Usa la misma lógica de
    identidad que el formulario: si ya existe (misma CURP) o hay un perfil de laboratorio sin CURP con exactamente su
    nombre, NO crea un duplicado: responde 409 para que se confirme (`confirmar_actualizacion`) y entonces actualiza
    ese perfil (el perfil de laboratorio adopta la CURP y conserva sus resultados).
    """
    sexo = {"M": "M", "MASCULINO": "M", "H": "M", "F": "F", "FEMENINO": "F"}.get(payload.sexo.strip().upper())
    if not sexo:
        raise _invalido("sexo", "debe ser M o F")
    if payload.fecha_nacimiento > date.today() or payload.fecha_nacimiento.year < 1900:
        raise _invalido("fecha_nacimiento", "fecha no válida")

    curp = None
    if payload.curp and payload.curp.strip():
        curp = curp_valida(payload.curp)
        if not curp:
            raise _invalido("curp", "no tiene el formato de una CURP (18 caracteres)")

    email = payload.email.strip().lower() if payload.email and payload.email.strip() else None
    if email and not validate_email(email):
        raise _invalido("email", "correo no válido")
    telefono = re.sub(r"\D", "", payload.telefono) if payload.telefono else None
    if telefono and not 8 <= len(telefono) <= 15:
        raise _invalido("telefono", "debe tener entre 8 y 15 dígitos")

    peso = estatura = None
    if payload.peso is not None:
        peso = normalizar_peso_kg(payload.peso)
        if peso is None:
            raise _invalido("peso", "fuera de rango (1 a 400 kg)")
    if payload.estatura is not None:
        estatura = normalizar_estatura_cm(payload.estatura)
        if estatura is None:
            raise _invalido("estatura", "fuera de rango (30 a 250 cm)")

    id_peticion = None
    if payload.id_peticion and payload.id_peticion.strip():
        id_peticion = normalizar_peticion(payload.id_peticion)
        if not id_peticion:
            raise _invalido("id_peticion", "debe tener 8 dígitos (o 10 con el modificador del UC-1000)")

    campana = None
    if payload.campana_id is not None:
        campana = (await db.execute(select(Campana).where(Campana.id == payload.campana_id))).scalar_one_or_none()
        if not campana:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Campaña no encontrada")

    # ¿A qué perfil pertenece? (CURP existente, perfil de laboratorio previo con el mismo nombre, o nuevo)
    identidad = await ResolvedorIdentidad(db).resolver(
        curp, payload.nombre, payload.apellido_paterno, payload.apellido_materno, sexo, payload.fecha_nacimiento)

    if identidad.paciente is not None and not payload.confirmar_actualizacion:
        existente = identidad.paciente
        datos_existente = {
            "codigo": "paciente_existente",
            "accion": identidad.accion,
            "paciente_id": existente.id,
            "nombre": f"{existente.nombre} {existente.apellido} {existente.apellido_materno or ''}".strip(),
            "identificacion": existente.identificacion,
            "revisar": identidad.revisar,
        }
        await db.rollback()      # el resolvedor pudo adoptar/fusionar: no se confirma nada sin la confirmación
        raise HTTPException(status.HTTP_409_CONFLICT, detail=datos_existente)

    c = payload.consentimientos
    paciente = await aplicar_datos(db, identidad.paciente, identidad.identificacion, {
        "nombre": payload.nombre, "apellido": payload.apellido_paterno, "apellido_materno": payload.apellido_materno,
        "sexo": sexo, "fecha_nacimiento": payload.fecha_nacimiento,
        "telefono": telefono, "whatsapp": telefono if c.whatsapp else None, "email": email,
        "domicilio": payload.domicilio, "codigo_postal": payload.codigo_postal,
        "estado_residencia": payload.estado_residencia, "municipio_residencia": payload.municipio_residencia,
        "peso": peso, "estatura": estatura, "derechohabiencia": payload.derechohabiencia,
        "suplemento_detalle": payload.suplemento, "tipo_agua": payload.tipo_agua,
        "cocina_agua_llave": payload.cocina_agua_llave,
        "padecimientos": ", ".join(p.strip() for p in payload.padecimientos if p.strip()) if payload.padecimientos else None,
        "email_consent": c.email, "whatsapp_consent": c.whatsapp, "result_delivery_consent": c.entrega_resultados,
        "questionnaire_source_id": f"alta_manual|{current_user.id}|{datetime.now():%Y%m%d%H%M%S}",
    })

    estado_peticion = await vincular_peticion(db, id_peticion, paciente, "manual") if id_peticion else None

    inscrito = False
    if campana:
        ya = (await db.execute(select(CampanaPaciente).where(
            CampanaPaciente.campana_id == campana.id, CampanaPaciente.paciente_id == paciente.id))).scalar_one_or_none()
        if not ya:
            db.add(CampanaPaciente(campana_id=campana.id, paciente_id=paciente.id, fuente_registro="alta_manual"))
            inscrito = True

    await db.commit()
    return {
        "paciente_id": paciente.id,
        "identificacion": paciente.identificacion,
        "accion": identidad.accion,
        "fusionados": identidad.fusionados,
        "revisar": identidad.revisar,
        "peticion": estado_peticion,
        "campana_inscrita": inscrito,
    }
