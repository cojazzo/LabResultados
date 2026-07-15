from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Resultado, Paciente, User
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

router = APIRouter(tags=["Resultados de Laboratorio"])

# Pydantic schemas para resultados
class PruebaInfo(BaseModel):
    codigo: str
    nombre: str
    unidad: str
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None
    categoria: str



class PacienteInfo(BaseModel):
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

class ResultadoResponse(BaseModel):
    id: int
    paciente: PacienteInfo
    prueba: PruebaInfo

    valor: Optional[float] = None
    valor_texto: Optional[str] = None
    interpretacion: Optional[str] = None
    fecha_toma: date
    fecha_resultado: Optional[date] = None
    observaciones: Optional[str] = None

    class Config:
        from_attributes = True

# --- Endpoints ---

@router.get("/resultados", response_model=List[ResultadoResponse])
async def get_resultados(
    response: Response,
    paciente_id: Optional[int] = None,
    prueba_id: Optional[int] = None,

    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    interpretacion: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene la lista de resultados filtrada y paginada.
    """
    offset = (page - 1) * limit
    conditions = []

    if paciente_id:
        conditions.append(Resultado.paciente_id == paciente_id)
    if prueba_id:
        conditions.append(Resultado.prueba_id == prueba_id)

    if fecha_desde:
        conditions.append(Resultado.fecha_toma >= fecha_desde)
    if fecha_hasta:
        conditions.append(Resultado.fecha_toma <= fecha_hasta)
    if interpretacion and interpretacion != "todos":
        conditions.append(Resultado.interpretacion == interpretacion)
        
    if search:
        search_terms = search.strip().split()
        patient_conditions = []
        for term in search_terms:
            term_filter = f"%{term}%"
            patient_conditions.append(
                or_(
                    Paciente.nombre.ilike(term_filter),
                    Paciente.apellido.ilike(term_filter),
                    Paciente.apellido_materno.ilike(term_filter),
                    Paciente.identificacion.ilike(term_filter)
                )
            )
        conditions.append(
            Resultado.paciente.has(
                and_(*patient_conditions)
            )
        )

    # Calcular total de registros antes de paginar
    count_stmt = select(func.count(Resultado.id)).where(and_(*conditions))
    total_res = await db.execute(count_stmt)
    total_count = total_res.scalar() or 0
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    stmt = (
        select(Resultado)
        .where(and_(*conditions))
        .options(
            selectinload(Resultado.paciente),
            selectinload(Resultado.prueba),

        )
        .order_by(desc(Resultado.fecha_toma), desc(Resultado.id))
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    resultados = result.scalars().all()
    
    # Formatear la salida para coincidir con el schema
    res_list = []
    for r in resultados:
        # Convertir Decimal a float para pydantic si es necesario
        valor_fl = float(r.valor) if r.valor is not None else None
        
        pr_min = float(r.prueba.valor_min) if r.prueba.valor_min is not None else None
        pr_max = float(r.prueba.valor_max) if r.prueba.valor_max is not None else None

        res_list.append(
            ResultadoResponse(
                id=r.id,
                paciente=PacienteInfo(
                    id=r.paciente.id,
                    identificacion=r.paciente.identificacion,
                    nombre=r.paciente.nombre,
                    apellido=r.paciente.apellido,
                    fecha_nacimiento=r.paciente.fecha_nacimiento,
                    sexo=r.paciente.sexo,
                    telefono=r.paciente.telefono,
                    email=r.paciente.email,
                    whatsapp=r.paciente.whatsapp,
                    apellido_materno=r.paciente.apellido_materno,
                    domicilio=r.paciente.domicilio,
                    codigo_postal=r.paciente.codigo_postal,
                    estado_residencia=r.paciente.estado_residencia,
                    municipio_residencia=r.paciente.municipio_residencia,
                    peso=r.paciente.peso,
                    estatura=r.paciente.estatura,
                    derechohabiencia=r.paciente.derechohabiencia,
                    suplemento_detalle=r.paciente.suplemento_detalle,
                    tipo_agua=r.paciente.tipo_agua,
                    cocina_agua_llave=r.paciente.cocina_agua_llave,
                    padecimientos=r.paciente.padecimientos
                ),
                prueba=PruebaInfo(
                    codigo=r.prueba.codigo,
                    nombre=r.prueba.nombre,
                    unidad=r.prueba.unidad,
                    valor_min=pr_min,
                    valor_max=pr_max,
                    categoria=r.prueba.categoria
                ),

                valor=valor_fl,
                valor_texto=r.valor_texto,
                interpretacion=r.interpretacion,
                fecha_toma=r.fecha_toma,
                fecha_resultado=r.fecha_resultado,
                observaciones=r.observaciones
            )
        )
    return res_list

@router.get("/resultados/{id}", response_model=ResultadoResponse)
async def get_resultado(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el detalle de un resultado específico por su ID.
    """
    stmt = (
        select(Resultado)
        .where(Resultado.id == id)
        .options(
            selectinload(Resultado.paciente),
            selectinload(Resultado.prueba),

        )
    )
    result = await db.execute(stmt)
    r = result.scalar_one_or_none()
    
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resultado con ID {id} no encontrado"
        )
        
    valor_fl = float(r.valor) if r.valor is not None else None
    pr_min = float(r.prueba.valor_min) if r.prueba.valor_min is not None else None
    pr_max = float(r.prueba.valor_max) if r.prueba.valor_max is not None else None

    return ResultadoResponse(
        id=r.id,
        paciente=PacienteInfo(
            id=r.paciente.id,
            identificacion=r.paciente.identificacion,
            nombre=r.paciente.nombre,
            apellido=r.paciente.apellido,
            fecha_nacimiento=r.paciente.fecha_nacimiento,
            sexo=r.paciente.sexo,
            telefono=r.paciente.telefono,
            email=r.paciente.email,
            whatsapp=r.paciente.whatsapp,
            apellido_materno=r.paciente.apellido_materno,
            domicilio=r.paciente.domicilio,
            codigo_postal=r.paciente.codigo_postal,
            estado_residencia=r.paciente.estado_residencia,
            municipio_residencia=r.paciente.municipio_residencia,
            peso=r.paciente.peso,
            estatura=r.paciente.estatura,
            derechohabiencia=r.paciente.derechohabiencia,
            suplemento_detalle=r.paciente.suplemento_detalle,
            tipo_agua=r.paciente.tipo_agua,
            cocina_agua_llave=r.paciente.cocina_agua_llave,
            padecimientos=r.paciente.padecimientos
        ),
        prueba=PruebaInfo(
            codigo=r.prueba.codigo,
            nombre=r.prueba.nombre,
            unidad=r.prueba.unidad,
            valor_min=pr_min,
            valor_max=pr_max,
            categoria=r.prueba.categoria
        ),

        valor=valor_fl,
        valor_texto=r.valor_texto,
        interpretacion=r.interpretacion,
        fecha_toma=r.fecha_toma,
        fecha_resultado=r.fecha_resultado,
        observaciones=r.observaciones
    )

@router.get("/pacientes", response_model=List[PacienteInfo])
async def get_pacientes(
    search: str = Query("", description="Búsqueda por nombre, apellido o identificación"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el listado de pacientes con opción de búsqueda.
    """
    stmt = select(Paciente)
    if search:
        search_terms = search.strip().split()
        for term in search_terms:
            term_filter = f"%{term}%"
            stmt = stmt.where(
                or_(
                    Paciente.nombre.ilike(term_filter),
                    Paciente.apellido.ilike(term_filter),
                    Paciente.apellido_materno.ilike(term_filter),
                    Paciente.identificacion.ilike(term_filter)
                )
            )
    stmt = stmt.order_by(Paciente.apellido, Paciente.nombre)
    result = await db.execute(stmt)
    pacientes = result.scalars().all()
    return pacientes

@router.get("/pacientes/{id}/resultados", response_model=List[ResultadoResponse])
async def get_paciente_resultados(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todos los resultados asociados a un paciente específico.
    """
    stmt = (
        select(Resultado)
        .where(Resultado.paciente_id == id)
        .options(
            selectinload(Resultado.paciente),
            selectinload(Resultado.prueba),

        )
        .order_by(desc(Resultado.fecha_toma), desc(Resultado.id))
    )
    result = await db.execute(stmt)
    resultados = result.scalars().all()
    
    res_list = []
    for r in resultados:
        valor_fl = float(r.valor) if r.valor is not None else None
        pr_min = float(r.prueba.valor_min) if r.prueba.valor_min is not None else None
        pr_max = float(r.prueba.valor_max) if r.prueba.valor_max is not None else None

        res_list.append(
            ResultadoResponse(
                id=r.id,
                paciente=PacienteInfo(
                    id=r.paciente.id,
                    identificacion=r.paciente.identificacion,
                    nombre=r.paciente.nombre,
                    apellido=r.paciente.apellido,
                    fecha_nacimiento=r.paciente.fecha_nacimiento,
                    sexo=r.paciente.sexo,
                    telefono=r.paciente.telefono,
                    email=r.paciente.email,
                    whatsapp=r.paciente.whatsapp,
                    apellido_materno=r.paciente.apellido_materno,
                    domicilio=r.paciente.domicilio,
                    codigo_postal=r.paciente.codigo_postal,
                    estado_residencia=r.paciente.estado_residencia,
                    municipio_residencia=r.paciente.municipio_residencia,
                    peso=r.paciente.peso,
                    estatura=r.paciente.estatura,
                    derechohabiencia=r.paciente.derechohabiencia,
                    suplemento_detalle=r.paciente.suplemento_detalle,
                    tipo_agua=r.paciente.tipo_agua,
                    cocina_agua_llave=r.paciente.cocina_agua_llave,
                    padecimientos=r.paciente.padecimientos
                ),
                prueba=PruebaInfo(
                    codigo=r.prueba.codigo,
                    nombre=r.prueba.nombre,
                    unidad=r.prueba.unidad,
                    valor_min=pr_min,
                    valor_max=pr_max,
                    categoria=r.prueba.categoria
                ),

                valor=valor_fl,
                valor_texto=r.valor_texto,
                interpretacion=r.interpretacion,
                fecha_toma=r.fecha_toma,
                fecha_resultado=r.fecha_resultado,
                observaciones=r.observaciones
            )
        )
    return res_list
