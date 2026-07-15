"""
Fixtures de pytest para los tests del backend.

Provee:
- Motor de base de datos de prueba (SQLite async en memoria)
- Sesión de base de datos de prueba
- Aplicación FastAPI con la BD de prueba inyectada
- Cliente httpx async
- Headers de autenticación con token JWT válido
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Asegurar que el backend está en el path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Forzar DATABASE_URL de test antes de importar la app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_lab.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"


@pytest.fixture(scope="session")
def event_loop():
    """Crear un event loop para toda la sesión de tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Motor de base de datos de prueba."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from app.models import Base

        test_engine = create_async_engine(
            "sqlite+aiosqlite:///./test_lab.db",
            echo=False,
        )

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield test_engine

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await test_engine.dispose()

        # Limpiar archivo de test
        test_db = Path("./test_lab.db")
        if test_db.exists():
            test_db.unlink()
    except ImportError:
        pytest.skip("App models not yet available")


@pytest_asyncio.fixture
async def db_session(engine):
    """Sesión de base de datos para cada test."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            yield session
            await session.rollback()
    except ImportError:
        pytest.skip("SQLAlchemy async not available")


@pytest_asyncio.fixture(scope="session")
async def app(engine):
    """Aplicación FastAPI configurada para tests."""
    try:
        from app.main import app as fastapi_app
        from app.database import get_db
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def override_get_db() -> AsyncGenerator:
            async with async_session() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db

        yield fastapi_app

        fastapi_app.dependency_overrides.clear()
    except ImportError:
        pytest.skip("App not yet available")


@pytest_asyncio.fixture
async def client(app):
    """Cliente httpx async para hacer requests a la app."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def seed_admin(engine):
    """Crear usuario admin para tests."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select
        from app.models import User
        from app.core.security import get_password_hash

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            async with session.begin():
                existing = await session.execute(
                    select(User).where(User.username == "admin")
                )
                if not existing.scalar_one_or_none():
                    admin = User(
                        username="admin",
                        email="admin@test.com",
                        hashed_password=get_password_hash("admin123"),
                        nombre_completo="Admin Test",
                        is_active=True,
                        is_superuser=True,
                    )
                    session.add(admin)
            await session.commit()
    except ImportError:
        pytest.skip("App models not available for seeding")


@pytest_asyncio.fixture
async def auth_headers(client, seed_admin) -> dict:
    """Headers con token JWT válido para requests autenticados."""
    response = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
