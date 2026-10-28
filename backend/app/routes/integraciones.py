from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_or_system
from app.database import get_db
from app.services.tamiz_sync import CICLO_DEFAULT, sincronizar_alumnos

router = APIRouter(prefix="/integraciones/tamiz", tags=["Integración tamiz-escolar"])


class AlumnoTamiz(BaseModel):
    folio: str
    curp: Optional[str] = None
    nombres: str
    primer_apellido: Optional[str] = None
    segundo_apellido: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    provisional: bool = False
    cct: Optional[str] = None
    escuela: Optional[str] = None
    subnivel: Optional[str] = None
    municipio: Optional[str] = None
    localidad: Optional[str] = None
    turno: Optional[str] = None
    grado: Optional[int] = None
    grupo: Optional[str] = None
    zona_escolar: Optional[str] = None
    ronda: Optional[int] = None
    fecha_evaluacion: Optional[date] = None
    peso_kg: Optional[float] = None
    talla_cm: Optional[float] = None


class RondaTamiz(BaseModel):
    numero: int
    inicio: Optional[date] = None
    fin: Optional[date] = None
    seg_muestra_inicio: Optional[date] = None
    seg_muestra_fin: Optional[date] = None


class CampanaTamiz(BaseModel):
    ciclo: str = CICLO_DEFAULT
    rondas: Optional[List[RondaTamiz]] = None
    total_padron: Optional[int] = None


class SincronizarRequest(BaseModel):
    campana: CampanaTamiz = Field(default_factory=CampanaTamiz)
    alumnos: List[AlumnoTamiz] = Field(max_length=2000)


@router.post("/alumnos")
async def sincronizar(
    payload: SincronizarRequest,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(get_current_user_or_system),
):
    """
    Sincroniza alumnos de tamiz-escolar (upsert idempotente por folio) y los inscribe en la campaña
    "Secundarias <ciclo>". Pensado para n8n (clave de sistema) o carga manual.
    """
    rondas = [r.model_dump(mode="json") for r in payload.campana.rondas] if payload.campana.rondas else None
    resumen = await sincronizar_alumnos(
        db,
        [a.model_dump() for a in payload.alumnos],
        ciclo=payload.campana.ciclo,
        rondas=rondas,
        total_padron=payload.campana.total_padron,
    )
    await db.commit()
    return resumen
