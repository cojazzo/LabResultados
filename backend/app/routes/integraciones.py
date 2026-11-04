from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_or_system
from app.database import get_db
from sqlalchemy import select

from app.models import Lote, Paciente
from app.services.excel_parser import procesar_df_tamizaje
from app.services.peticiones import vincular_peticion
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


# ---------------------------------------------------------------------------
# Google Forms (vía n8n): alta automática de perfiles con datos personales y clínicos
# ---------------------------------------------------------------------------

router_forms = APIRouter(prefix="/integraciones/forms", tags=["Integración Google Forms"])


class RespuestaForms(BaseModel):
    id_respuesta: str = Field(min_length=1, max_length=120,
                              description="Identificador estable de la respuesta (p. ej. hoja + marca temporal)")
    campos: Dict[str, Any] = Field(description="Columna de la hoja del Forms -> valor, tal como viene en la hoja")


class RespuestasFormsRequest(BaseModel):
    origen: str = Field(default="google_forms", max_length=60)
    respuestas: List[RespuestaForms] = Field(min_length=1, max_length=200)


@router_forms.post("/respuestas")
async def recibir_respuestas_forms(
    payload: RespuestasFormsRequest,
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_current_user_or_system),
):
    """
    Recibe respuestas del Google Forms de tamizaje (una o varias) y crea/actualiza el perfil de cada persona,
    uniéndola con los resultados de la tira y el Vitros que ya existan (por CURP, o por nombre exacto
    cuando el perfil de laboratorio todavía no tenía CURP). Idempotente por `id_respuesta`.
    Las columnas son las mismas que las del Excel del Forms. n8n solo reenvía; las reglas viven aquí.
    """
    df = pd.DataFrame([r.campos for r in payload.respuestas])
    df = df.replace("", None)
    lote = Lote(
        nombre=f"Google Forms (n8n) {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        descripcion=f"Alta automática desde {payload.origen}: {len(payload.respuestas)} respuesta(s)",
        usuario_id=getattr(auth, "id", None),
        estado="procesando", total_registros=len(payload.respuestas),
        registros_exitosos=0, registros_error=0,
    )
    db.add(lote)
    await db.commit()
    await db.refresh(lote)

    out = await procesar_df_tamizaje(db, df, lote, ids_respuesta=[r.id_respuesta for r in payload.respuestas])
    return {
        "lote_id": lote.id,
        "exitosos": out["resumen"]["exitosos"],
        "erroneos": out["resumen"]["erroneos"],
        "respuestas": out["detalles"],
        "errores": out["errores"],
        "por_revisar": sum(1 for d in out["detalles"] if d.get("revisar")),
    }


# ---------------------------------------------------------------------------
# Peticiones del servicio externo: vincular el ID de petición (tira) con un paciente
# ---------------------------------------------------------------------------

router_peticiones = APIRouter(prefix="/integraciones/peticiones", tags=["Peticiones del servicio externo"])


class VinculoPeticion(BaseModel):
    id_peticion: str = Field(min_length=8, max_length=12, description="8 dígitos (o 10 con el modificador del UC-1000)")
    identificacion: str = Field(min_length=3, max_length=60, description="CURP o folio del paciente")


class VincularPeticionesRequest(BaseModel):
    vinculos: List[VinculoPeticion] = Field(min_length=1, max_length=200)


@router_peticiones.post("")
async def vincular_peticiones(
    payload: VincularPeticionesRequest,
    db: AsyncSession = Depends(get_db),
    _auth=Depends(get_current_user_or_system),
):
    """
    Vincula IDs de petición con pacientes para que las filas de la tira (ID = "17" + petición) se carguen en su
    perfil aunque no haya Excel de Vitros (cuando no se pidió creatinina). Idempotente; una petición ya vinculada
    a otro paciente se reporta como conflicto y no se cambia.
    """
    resultados = []
    for v in payload.vinculos:
        ident = v.identificacion.strip().upper()
        paciente = (await db.execute(select(Paciente).where(
            (Paciente.identificacion == ident) | (Paciente.folio_tamiz == ident)))).scalars().first()
        if not paciente:
            resultados.append({"id_peticion": v.id_peticion, "estado": "paciente_no_encontrado"})
            continue
        estado = await vincular_peticion(db, v.id_peticion, paciente, "api")
        resultados.append({"id_peticion": v.id_peticion, "estado": estado, "paciente_id": paciente.id})
    await db.commit()
    return {"vinculos": resultados}
