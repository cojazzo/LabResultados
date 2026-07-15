from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.database import get_db
from app.models import Prueba, Medico, User
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

# Router para el Catálogo de Pruebas
pruebas_router = APIRouter(prefix="/catalogo", tags=["Catálogo de Pruebas"])

# Router para Médicos
medicos_router = APIRouter(prefix="/medicos", tags=["Médicos"])

# Pydantic Schemas
class PruebaCreateUpdate(BaseModel):
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None
    valor_critico_min: Optional[float] = None
    valor_critico_max: Optional[float] = None
    metodo: Optional[str] = None
    activa: Optional[bool] = True

class PruebaResponse(BaseModel):
    id: int
    codigo: str
    nombre: str
    categoria: str
    unidad: str
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None
    valor_critico_min: Optional[float] = None
    valor_critico_max: Optional[float] = None
    metodo: Optional[str] = None
    activa: bool

    class Config:
        from_attributes = True

class MedicoResponse(BaseModel):
    id: int
    cedula: str
    nombre: str
    apellido: Optional[str] = None
    especialidad: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


# --- Endpoints de Pruebas ---

@pruebas_router.get("/pruebas", response_model=List[PruebaResponse])
async def list_pruebas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todas las pruebas del catálogo.
    """
    stmt = select(Prueba).order_by(Prueba.categoria, Prueba.nombre)
    result = await db.execute(stmt)
    pruebas = result.scalars().all()
    
    # Formatear Decimal a float para pydantic
    res = []
    for p in pruebas:
        res.append(
            PruebaResponse(
                id=p.id,
                codigo=p.codigo,
                nombre=p.nombre,
                categoria=p.categoria,
                unidad=p.unidad,
                valor_min=float(p.valor_min) if p.valor_min is not None else None,
                valor_max=float(p.valor_max) if p.valor_max is not None else None,
                valor_critico_min=float(p.valor_critico_min) if p.valor_critico_min is not None else None,
                valor_critico_max=float(p.valor_critico_max) if p.valor_critico_max is not None else None,
                metodo=p.metodo,
                activa=p.activa
            )
        )
    return res

@pruebas_router.post("/pruebas", response_model=PruebaResponse, status_code=status.HTTP_201_CREATED)
async def create_prueba(
    req: PruebaCreateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea una nueva prueba en el catálogo (Solo administradores/químicos).
    """
    if current_user.rol not in ("admin", "quimico") and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar el catálogo"
        )
        
    # Verificar duplicado
    stmt = select(Prueba).where(Prueba.codigo == req.codigo)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una prueba con el código '{req.codigo}'"
        )

    nueva_prueba = Prueba(
        codigo=req.codigo,
        nombre=req.nombre,
        categoria=req.categoria,
        unidad=req.unidad,
        valor_min=Decimal(str(req.valor_min)) if req.valor_min is not None else None,
        valor_max=Decimal(str(req.valor_max)) if req.valor_max is not None else None,
        valor_critico_min=Decimal(str(req.valor_critico_min)) if req.valor_critico_min is not None else None,
        valor_critico_max=Decimal(str(req.valor_critico_max)) if req.valor_critico_max is not None else None,
        metodo=req.metodo,
        activa=req.activa
    )
    db.add(nueva_prueba)
    await db.commit()
    await db.refresh(nueva_prueba)
    
    return PruebaResponse(
        id=nueva_prueba.id,
        codigo=nueva_prueba.codigo,
        nombre=nueva_prueba.nombre,
        categoria=nueva_prueba.categoria,
        unidad=nueva_prueba.unidad,
        valor_min=float(nueva_prueba.valor_min) if nueva_prueba.valor_min is not None else None,
        valor_max=float(nueva_prueba.valor_max) if nueva_prueba.valor_max is not None else None,
        valor_critico_min=float(nueva_prueba.valor_critico_min) if nueva_prueba.valor_critico_min is not None else None,
        valor_critico_max=float(nueva_prueba.valor_critico_max) if nueva_prueba.valor_critico_max is not None else None,
        metodo=nueva_prueba.metodo,
        activa=nueva_prueba.activa
    )

@pruebas_router.put("/pruebas/{id}", response_model=PruebaResponse)
async def update_prueba(
    id: int,
    req: PruebaCreateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Edita una prueba existente en el catálogo (Solo administradores/químicos).
    """
    if current_user.rol not in ("admin", "quimico") and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar el catálogo"
        )
        
    stmt = select(Prueba).where(Prueba.id == id)
    result = await db.execute(stmt)
    prueba = result.scalar_one_or_none()
    
    if not prueba:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prueba con ID {id} no encontrada"
        )

    # Actualizar valores
    prueba.codigo = req.codigo
    prueba.nombre = req.nombre
    prueba.categoria = req.categoria
    prueba.unidad = req.unidad
    prueba.valor_min = Decimal(str(req.valor_min)) if req.valor_min is not None else None
    prueba.valor_max = Decimal(str(req.valor_max)) if req.valor_max is not None else None
    prueba.valor_critico_min = Decimal(str(req.valor_critico_min)) if req.valor_critico_min is not None else None
    prueba.valor_critico_max = Decimal(str(req.valor_critico_max)) if req.valor_critico_max is not None else None
    prueba.metodo = req.metodo
    prueba.activa = req.activa

    await db.commit()
    await db.refresh(prueba)
    
    return PruebaResponse(
        id=prueba.id,
        codigo=prueba.codigo,
        nombre=prueba.nombre,
        categoria=prueba.categoria,
        unidad=prueba.unidad,
        valor_min=float(prueba.valor_min) if prueba.valor_min is not None else None,
        valor_max=float(prueba.valor_max) if prueba.valor_max is not None else None,
        valor_critico_min=float(prueba.valor_critico_min) if prueba.valor_critico_min is not None else None,
        valor_critico_max=float(prueba.valor_critico_max) if prueba.valor_critico_max is not None else None,
        metodo=prueba.metodo,
        activa=prueba.activa
    )

# --- Endpoints de Médicos ---

@medicos_router.get("", response_model=List[MedicoResponse])
async def list_medicos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los médicos registrados.
    """
    stmt = select(Medico).order_by(Medico.apellido, Medico.nombre)
    result = await db.execute(stmt)
    medicos = result.scalars().all()
    return medicos
