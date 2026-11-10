"""Alta manual de pacientes (POST /api/pacientes). Solo datos sintéticos."""
import pytest


def payload(**extra):
    base = {
        "nombre": "ALTA PRUEBA", "apellido_paterno": "UNO", "apellido_materno": "SINTETICO", "sexo": "F",
        "fecha_nacimiento": "2012-12-26", "curp": "TEST050505MASAAA05", "telefono": "449 000 0000",
        "email": "Sintetico@Example.Test", "domicilio": "Calle Falsa 123", "codigo_postal": "20000",
        "estado_residencia": "Aguascalientes", "municipio_residencia": "Aguascalientes",
        "peso": 50, "estatura": 1.4, "derechohabiencia": "IMSS", "suplemento": "No",
        "tipo_agua": "agua rellanada", "cocina_agua_llave": "No",
        "padecimientos": ["Obesidad", "Diabetes"],
        "consentimientos": {"email": True, "whatsapp": True, "entrega_resultados": True},
    }
    base.update(extra)
    return base


@pytest.mark.asyncio
async def test_requiere_sesion(client):
    r = await client.post("/api/pacientes", json=payload())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_crea_con_datos_normalizados(client, auth_headers):
    r = await client.post("/api/pacientes", json=payload(), headers=auth_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accion"] == "creado" and j["identificacion"] == "TEST050505MASAAA05"
    p = (await client.get(f"/api/pacientes/{j['paciente_id']}", headers=auth_headers)).json()
    assert p["estatura"] == 140.0 and p["peso"] == 50.0            # 1.4 m -> 140 cm
    assert p["sexo"] == "F" and p["email"] == "sintetico@example.test" and p["telefono"] == "4490000000"
    assert p["padecimientos"] == "Obesidad, Diabetes" and p["apellido_materno"] == "SINTETICO"


@pytest.mark.asyncio
async def test_si_ya_existe_pide_confirmacion_y_luego_actualiza(client, auth_headers):
    base = payload(nombre="EXISTE", apellido_paterno="DOS", curp="TEST060606HASBBB06", sexo="M")
    creado = (await client.post("/api/pacientes", json=base, headers=auth_headers)).json()

    r = await client.post("/api/pacientes", json={**base, "telefono": "4491111111"}, headers=auth_headers)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["codigo"] == "paciente_existente" and d["paciente_id"] == creado["paciente_id"]
    antes = (await client.get(f"/api/pacientes/{creado['paciente_id']}", headers=auth_headers)).json()
    assert antes["telefono"] == "4490000000"                        # el 409 no cambió nada

    r = await client.post("/api/pacientes", json={**base, "telefono": "4491111111", "confirmar_actualizacion": True},
                          headers=auth_headers)
    assert r.status_code == 200 and r.json()["accion"] == "actualizado"
    assert (await client.get(f"/api/pacientes/{creado['paciente_id']}", headers=auth_headers)).json()["telefono"] == "4491111111"


@pytest.mark.asyncio
async def test_perfil_de_laboratorio_sin_curp_adopta_la_curp(client, auth_headers, app):
    from app.database import get_db
    from app.models import Paciente

    async for sesion in app.dependency_overrides[get_db]():
        lab = Paciente(identificacion="SYN-ZZZZZZZZZZZZZZ", nombre="ADOPTA", apellido="TRES UNICO",
                       origen="servicio_externo")
        sesion.add(lab)
        await sesion.commit()
        lab_id = lab.id
        break

    body = payload(nombre="ADOPTA", apellido_paterno="TRES", apellido_materno="UNICO", curp="TEST070707MASCCC07")
    r = await client.post("/api/pacientes", json=body, headers=auth_headers)
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["accion"] == "adoptado" and d["paciente_id"] == lab_id
    assert (await client.get(f"/api/pacientes/{lab_id}", headers=auth_headers)).json()["identificacion"] == "SYN-ZZZZZZZZZZZZZZ"  # sin cambios

    r = await client.post("/api/pacientes", json={**body, "confirmar_actualizacion": True}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["accion"] == "adoptado" and r.json()["paciente_id"] == lab_id
    adoptado = (await client.get(f"/api/pacientes/{lab_id}", headers=auth_headers)).json()
    assert adoptado["identificacion"] == "TEST070707MASCCC07" and adoptado["peso"] == 50.0     # mismo perfil, ya con CURP


@pytest.mark.asyncio
async def test_validaciones(client, auth_headers):
    casos = {
        "curp": {"curp": "NO-ES-CURP"},
        "estatura": {"estatura": 500},
        "peso": {"peso": 0},
        "email": {"email": "no es correo"},
        "sexo": {"sexo": "X"},
        "telefono": {"telefono": "123"},
        "id_peticion": {"id_peticion": "123"},
        "fecha_nacimiento": {"fecha_nacimiento": "2999-01-01"},
    }
    for campo, extra in casos.items():
        r = await client.post("/api/pacientes", json=payload(**{"curp": "TEST080808HASDDD08", **extra}), headers=auth_headers)
        assert r.status_code == 422, (campo, r.text)
        assert campo in str(r.json()["detail"]), (campo, r.text)


@pytest.mark.asyncio
async def test_vincula_peticion_e_inscribe_en_campana(client, auth_headers):
    camp = (await client.post("/api/campanas", json={"nombre": "Campana alta prueba", "tipo": "servicio_externo"},
                              headers=auth_headers))
    assert camp.status_code in (200, 201), camp.text
    campana_id = camp.json()["id"]
    body = payload(nombre="PETICION", apellido_paterno="CUATRO", curp="TEST090909HASEEE09", sexo="M",
                   id_peticion="1799922299", campana_id=campana_id)
    r = await client.post("/api/pacientes", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["peticion"] == "vinculada" and r.json()["campana_inscrita"] is True

    r2 = await client.post("/api/pacientes", json={**body, "confirmar_actualizacion": True}, headers=auth_headers)
    assert r2.json()["peticion"] == "ya_vinculada" and r2.json()["campana_inscrita"] is False

    r3 = await client.post("/api/pacientes", json={**body, "campana_id": 999999}, headers=auth_headers)
    assert r3.status_code == 404
