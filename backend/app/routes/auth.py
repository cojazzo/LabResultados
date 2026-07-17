from datetime import timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_user
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Pydantic schemas locales para auth
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    nombre_completo: str
    rol: str = "tecnico"  # admin, tecnico, quimico

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    password: Optional[str] = None  # Si viene, se actualiza el hash

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    nombre_completo: str
    rol: str
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Inicio de sesión por formulario (OAuth2 compatible).
    """
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo"
        )
        
    access_token = create_access_token(subject=user.username)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Registrar un nuevo usuario (Solo administradores).
    """
    if current_user.rol != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para registrar usuarios"
        )

    # Verificar si el usuario o email ya existen
    username_exists = await db.execute(select(User).where(User.username == user_data.username))
    if username_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya está registrado"
        )
        
    email_exists = await db.execute(select(User).where(User.email == user_data.email))
    if email_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado"
        )

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        nombre_completo=user_data.nombre_completo,
        rol=user_data.rol,
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Retorna el perfil del usuario autenticado actual.
    """
    return current_user

# ── Gestión de usuarios (solo admin) ─────────────────────────────────

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los usuarios del sistema (Solo administradores).
    """
    if current_user.rol != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver los usuarios"
        )
    result = await db.execute(select(User).order_by(User.nombre_completo))
    return result.scalars().all()

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza datos de un usuario (Solo administradores).
    """
    if current_user.rol != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para editar usuarios"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_data.email is not None:
        # Verificar que el email no esté en uso por otro usuario
        existing = await db.execute(
            select(User).where(User.email == user_data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="El correo ya está registrado por otro usuario")
        user.email = user_data.email

    if user_data.nombre_completo is not None:
        user.nombre_completo = user_data.nombre_completo

    if user_data.rol is not None:
        user.rol = user_data.rol

    if user_data.password:
        user.hashed_password = get_password_hash(user_data.password)

    await db.commit()
    await db.refresh(user)
    return user

@router.patch("/users/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_user_active(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Activa o desactiva un usuario (Solo administradores).
    No permite desactivarse a sí mismo.
    """
    if current_user.rol != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar usuarios"
        )

    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puede desactivar su propia cuenta"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    return user
