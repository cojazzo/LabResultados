"""
Tests de la API con httpx AsyncClient.

Ejecutar con: pytest backend/tests/test_api.py -v
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seed_admin):
    """Login con credenciales válidas debe retornar un token."""
    response = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient, seed_admin):
    """Login con contraseña incorrecta debe retornar 401."""
    response = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "wrong_password"},
    )
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_get_dashboard_unauthorized(client: AsyncClient):
    """Acceder al dashboard sin token debe retornar 401."""
    response = await client.get("/api/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_pruebas(client: AsyncClient, auth_headers: dict):
    """Listar catálogo de pruebas con autenticación válida."""
    response = await client.get("/api/catalogo/pruebas", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_pruebas_unauthorized(client: AsyncClient):
    """Listar pruebas sin token debe retornar 401."""
    response = await client.get("/api/catalogo/pruebas")
    assert response.status_code == 401



@pytest.mark.asyncio
async def test_login_returns_valid_token(client: AsyncClient, seed_admin):
    """El token devuelto por login debe funcionar para endpoints protegidos."""
    # Login
    login_response = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Usar el token
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
