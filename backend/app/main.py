import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import engine, Base
from app.core.security import get_password_hash

# Importar routers
from app.routes.auth import router as auth_router
from app.routes.excel_upload import router as upload_router
from app.routes.resultados import router as resultados_router
from app.routes.reportes import router as reportes_router
from app.routes.envios import router as envios_router
from app.routes.dashboard import router as dashboard_router
from app.routes.catalogos import pruebas_router, medicos_router
from app.routes.pacientes import router as pacientes_router
from app.routes.automation import router as automation_router
from app.routes.quimicos import router as quimicos_router

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    # 1. Asegurar directorios de almacenamiento
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    os.makedirs("./storage/emails", exist_ok=True)
    os.makedirs("./storage/whatsapp", exist_ok=True)
    
    # 2. Crear tablas de base de datos si es SQLite (desarrollo local rápido)
    # Para producción, se usarían migraciones Alembic
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        # 3. Insertar usuario administrador por defecto si no existe
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        from app.models import User
        from app.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(User).where(User.username == "admin")
                result = await session.execute(stmt)
                admin_user = result.scalar_one_or_none()
                
                if not admin_user:
                    new_admin = User(
                        username="admin",
                        email="admin@labsanrafael.com",
                        hashed_password=get_password_hash("admin123"),
                        nombre_completo="Administrador General",
                        rol="admin",
                        is_active=True,
                        is_superuser=True
                    )
                    session.add(new_admin)
                    print("✅ Usuario admin creado por defecto (admin / admin123)")
    yield
    # Shutdown actions
    await engine.dispose()

app = FastAPI(
    title="LabResultados API",
    description="Sistema de Gestión de Resultados de Laboratorio Clínico",
    version="1.0.0",
    lifespan=lifespan
)

# Configuración de CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar almacenamiento estático para PDFs
# Esto permite acceder directamente a los PDFs vía http://localhost:8000/storage/pdfs/...
os.makedirs("./storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="./storage"), name="storage")

# Incluir routers bajo el prefijo /api
app.include_router(auth_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(resultados_router, prefix="/api")
app.include_router(reportes_router, prefix="/api")
app.include_router(envios_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(pruebas_router, prefix="/api")
app.include_router(pacientes_router, prefix="/api")
app.include_router(medicos_router, prefix="/api")
app.include_router(automation_router, prefix="/api")
app.include_router(quimicos_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "LabResultados Backend"}
