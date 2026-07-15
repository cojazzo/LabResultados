from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Quimico, User
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/quimicos", tags=["Químicos"])

class QuimicoCreate(BaseModel):
    nombre_completo: str
    cedula: str
    activo: bool = True

class QuimicoResponse(BaseModel):
    id: int
    nombre_completo: str
    cedula: str
    activo: bool

    class Config:
        from_attributes = True

def require_admin(current_user: User):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")

@router.get("", response_model=List[QuimicoResponse])
async def get_quimicos(db: AsyncSession = Depends(get_db)):
    stmt = select(Quimico).order_by(Quimico.nombre_completo)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/activos", response_model=List[QuimicoResponse])
async def get_quimicos_activos(db: AsyncSession = Depends(get_db)):
    stmt = select(Quimico).where(Quimico.activo == True).order_by(Quimico.nombre_completo)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=QuimicoResponse)
async def create_quimico(
    quimico: QuimicoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    
    # Check if cedula exists
    stmt = select(Quimico).where(Quimico.cedula == quimico.cedula)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ya existe un químico con esa cédula")
        
    db_quimico = Quimico(**quimico.model_dump())
    db.add(db_quimico)
    await db.commit()
    await db.refresh(db_quimico)
    return db_quimico

@router.put("/{quimico_id}", response_model=QuimicoResponse)
async def update_quimico(
    quimico_id: int,
    quimico: QuimicoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    
    stmt = select(Quimico).where(Quimico.id == quimico_id)
    res = await db.execute(stmt)
    db_quimico = res.scalar_one_or_none()
    
    if not db_quimico:
        raise HTTPException(status_code=404, detail="Químico no encontrado")
        
    # Check cedula unicity if changed
    if db_quimico.cedula != quimico.cedula:
        stmt_check = select(Quimico).where(Quimico.cedula == quimico.cedula)
        res_check = await db.execute(stmt_check)
        if res_check.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Ya existe otro químico con esa cédula")
            
    db_quimico.nombre_completo = quimico.nombre_completo
    db_quimico.cedula = quimico.cedula
    db_quimico.activo = quimico.activo
    
    await db.commit()
    await db.refresh(db_quimico)
    return db_quimico
