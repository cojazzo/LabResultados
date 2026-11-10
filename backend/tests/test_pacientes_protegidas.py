"""Las rutas de pacientes ya no se pueden usar sin credenciales. Solo datos sintéticos."""
import pytest

CUESTIONARIO = {"curp": "TEST101010HASFFF10", "nombre": "PROTEGIDA", "apellido_paterno": "CINCO", "sexo": "Femenino"}


@pytest.mark.asyncio
async def test_sin_credenciales_las_tres_rutas_responden_401(client):
    assert (await client.post("/api/pacientes/cuestionario", json=CUESTIONARIO)).status_code == 401
    assert (await client.get("/api/pacientes/1")).status_code == 401
    assert (await client.patch("/api/pacientes/1/cuestionario", json={"telefono": "4490000000"})).status_code == 401


@pytest.mark.asyncio
async def test_con_clave_de_sistema_n8n_puede_registrar_el_cuestionario(client):
    from app.config import get_settings
    sistema = {"Authorization": get_settings().SYSTEM_API_KEY}
    r = await client.post("/api/pacientes/cuestionario", json=CUESTIONARIO, headers=sistema)
    assert r.status_code == 200, r.text
    pid = r.json()["paciente_id"]
    assert (await client.get(f"/api/pacientes/{pid}", headers=sistema)).status_code == 200


@pytest.mark.asyncio
async def test_con_sesion_de_usuario_se_lee_y_se_edita(client, auth_headers):
    r = await client.post("/api/pacientes/cuestionario", json={**CUESTIONARIO, "curp": "TEST111111HASGGG11"},
                          headers=auth_headers)
    pid = r.json()["paciente_id"]
    assert (await client.get(f"/api/pacientes/{pid}", headers=auth_headers)).json()["nombre"] == "PROTEGIDA"
    r = await client.patch(f"/api/pacientes/{pid}/cuestionario", json={"telefono": "4492222222"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["telefono"] == "4492222222"
    # un token falso no sirve
    falso = {"Authorization": "Bearer token-falso"}
    assert (await client.get(f"/api/pacientes/{pid}", headers=falso)).status_code == 401
