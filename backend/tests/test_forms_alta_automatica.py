"""Alta automática de perfiles desde Google Forms (vía n8n). Solo datos sintéticos."""
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select

from app.models import Lote, Paciente, Prueba, Resultado
from app.services.excel_parser import procesar_df_tamizaje, process_horizontal_excel
from app.services.tamiz_sync import resolver_folio, sincronizar_alumnos
from app.services.uc1000_parser import process_uc1000_csv
from tests.test_tamiz_integration import alumno, csv_tira, db, valores  # noqa: F401  (db es fixture)

CURP_C = "TEST030303HASCCC03"
CURP_D = "TEST040404MASDDD04"


def respuesta(curp=CURP_C, nombre="LUNA SOFIA", pat="PEREZ", mat="CARDENAS", sexo="Femenino", **extra):
    fila = {"Marca temporal": "27/10/2026 10:00:00", "Nombre": nombre, "Apellido paterno": pat,
            "Apellido materno": mat, "Sexo": sexo, "CURP": curp, "Fecha de nacimiento": "2012-12-26",
            "Correo electrónico": "sintetico@example.test", "Teléfono de contacto": "4490000000",
            "Peso": 50, "Estatura": 160, "Padecimientos (seleccionar 1 o varios)": "Ninguno"}
    fila.update(extra)
    return fila


async def enviar(db, filas, ids=None):
    lote = Lote(nombre="forms", descripcion="t", usuario_id=None, estado="procesando", total_registros=len(filas),
                registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.commit()
    df = pd.DataFrame(filas).replace("", None)
    return await procesar_df_tamizaje(db, df, lote, ids_respuesta=ids or [f"r{i}" for i in range(len(filas))])


async def pacientes(db):
    return (await db.execute(select(Paciente))).scalars().all()


async def perfil_lab(db, ident, nombre, apellido, **extra):
    """Perfil sin CURP como los que crean las cargas de laboratorio."""
    p = Paciente(identificacion=ident, nombre=nombre, apellido=apellido, origen="servicio_externo", **extra)
    db.add(p)
    await db.flush()
    return p


async def resultado(db, p, codigo, valor, fuente, fecha=date(2026, 10, 27)):
    pr = (await db.execute(select(Prueba).where(Prueba.codigo == codigo))).scalar_one_or_none()
    if not pr:
        pr = Prueba(codigo=codigo, nombre=codigo, categoria="Orina", unidad="x")
        db.add(pr)
        await db.flush()
    lote = Lote(nombre="l", descripcion="t", usuario_id=None, estado="completado")
    db.add(lote)
    await db.flush()
    db.add(Resultado(lote_id=lote.id, paciente_id=p.id, prueba_id=pr.id, valor=valor, interpretacion="normal",
                     fecha_toma=fecha, fecha_resultado=fecha, fuente=fuente))
    await db.flush()


@pytest.mark.asyncio
async def test_el_formulario_crea_el_perfil_y_despues_se_le_unen_tira_y_vitros(db):
    out = await enviar(db, [respuesta()])
    assert out["detalles"][0]["accion"] == "creado"
    (p,) = await pacientes(db)
    assert p.identificacion == CURP_C and p.email == "sintetico@example.test" and float(p.peso) == 50

    # llega la tira (ID = CURP) y el Vitros (NTS = CURP): todo cae en el mismo perfil y visita
    await process_uc1000_csv(db, csv_tira([(CURP_C, "27/10/2026", "100", "30")]), "tira.csv", 1)
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-27", "Número": "99921800", "Nombre del Paciente": "LUNA SOFIA",
                        "Apellidos": "PEREZ CARDENAS", "NTS": CURP_C, "CRE01": "125"}])
    await process_horizontal_excel(db, df, lote)
    assert len(await pacientes(db)) == 1
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 27))] == (125.0, "vitros")
    assert v[("ALBOR", date(2026, 10, 27))] == (30.0, "tira_uc1000")
    assert v[("ACR", date(2026, 10, 27))][0] == pytest.approx(24.0)


@pytest.mark.asyncio
async def test_perfil_de_laboratorio_sin_curp_adopta_la_curp_del_formulario(db):
    lab = await perfil_lab(db, "SYN-AAAAAAAAAAAAAA", "LUNA SOFIA", "PEREZ CARDENAS", fecha_nacimiento=date(2026, 10, 27))
    await resultado(db, lab, "CRE01", 125, "vitros")
    await db.commit()

    out = await enviar(db, [respuesta()])
    d = out["detalles"][0]
    assert d["accion"] == "adoptado" and d["paciente_id"] == lab.id
    (p,) = await pacientes(db)
    assert p.id == lab.id and p.identificacion == CURP_C                  # el mismo perfil, ahora con CURP
    assert p.fecha_nacimiento == date(2012, 12, 26) and p.email == "sintetico@example.test"
    assert (await valores(db, p.id))[("CRE01", date(2026, 10, 27))] == (125.0, "vitros")   # conserva sus resultados


@pytest.mark.asyncio
async def test_si_la_curp_ya_existe_se_fusiona_el_perfil_de_laboratorio_con_el_mismo_nombre(db):
    await enviar(db, [respuesta()])                                       # perfil con CURP (de un formulario previo)
    (con_curp,) = await pacientes(db)
    lab = await perfil_lab(db, "NTS-99921800", "LUNA SOFIA", "PEREZ CARDENAS")
    await resultado(db, lab, "CRE01", 125, "vitros")
    await db.commit()

    out = await enviar(db, [respuesta()], ids=["r-otra"])
    d = out["detalles"][0]
    assert d["accion"] == "fusionado" and d["fusionados"] == 1
    (p,) = await pacientes(db)
    assert p.id == con_curp.id
    assert (await valores(db, p.id))[("CRE01", date(2026, 10, 27))] == (125.0, "vitros")


@pytest.mark.asyncio
async def test_con_varios_candidatos_o_nombre_parecido_no_se_une_y_se_avisa(db):
    a = await perfil_lab(db, "SYN-AAAAAAAAAAAAAA", "LUNA SOFIA", "PEREZ CARDENAS")
    b = await perfil_lab(db, "SYN-BBBBBBBBBBBBBB", "LUNA SOFIA", "PEREZ CARDENAS")
    c = await perfil_lab(db, "SYN-CCCCCCCCCCCCCC", "MARIA FERNANDA", "LOPEZ RAMIREZ")
    await db.commit()

    out = await enviar(db, [respuesta(), respuesta(curp=CURP_D, nombre="MARIA FERNANDO", pat="LOPEZ", mat="RAMIREZ")],
                       ids=["x1", "x2"])
    d1, d2 = out["detalles"]
    assert d1["accion"] == "creado" and len(d1["revisar"]) == 2        # ambiguo: no se une, se avisa
    assert d2["accion"] == "creado" and d2["revisar"][0]["id"] == c.id  # solo parecido: no se une, se avisa
    assert {p.id for p in await pacientes(db)} >= {a.id, b.id, c.id}
    assert out["resumen"]["exitosos"] == 2


@pytest.mark.asyncio
async def test_no_une_si_el_sexo_contradice_ni_toca_a_los_alumnos_del_padron(db):
    hombre = await perfil_lab(db, "SYN-AAAAAAAAAAAAAA", "LUNA SOFIA", "PEREZ CARDENAS", sexo="M")
    await sincronizar_alumnos(db, [alumno(curp=CURP_D, nombres="LUNA SOFIA", primer_apellido="PEREZ",
                                          segundo_apellido="CARDENAS", sexo="M")])
    await db.commit()

    out = await enviar(db, [respuesta(sexo="Femenino")])          # el perfil de laboratorio es M: no coincide
    assert out["detalles"][0]["accion"] == "creado"
    out = await enviar(db, [respuesta(curp=CURP_D, nombre="OTRO", pat="NOMBRE", mat="DISTINTO", sexo="Masculino")],
                       ids=["z"])
    alumno_padron = await resolver_folio(db, "S00000001")
    await db.refresh(alumno_padron)
    assert alumno_padron.nombre == "LUNA SOFIA" and alumno_padron.apellido == "PEREZ"   # tamiz manda su nombre
    assert alumno_padron.email == "sintetico@example.test"                                # pero sí suma los datos del formulario
    assert hombre.id in {p.id for p in await pacientes(db)}


@pytest.mark.asyncio
async def test_reenviar_la_misma_respuesta_es_idempotente(db):
    primera = await enviar(db, [respuesta()], ids=["fila-12"])
    segunda = await enviar(db, [respuesta()], ids=["fila-12"])
    assert primera["detalles"][0]["accion"] == "creado"
    assert segunda["detalles"][0]["accion"] == "sin_cambios"
    assert len(await pacientes(db)) == 1


@pytest.mark.asyncio
async def test_endpoint_exige_autenticacion_y_procesa_respuestas(client):
    from app.config import get_settings
    body = {"respuestas": [{"id_respuesta": "hoja1-2", "campos": respuesta()}]}
    assert (await client.post("/api/integraciones/forms/respuestas", json=body)).status_code == 401
    r = await client.post("/api/integraciones/forms/respuestas", json=body,
                          headers={"Authorization": get_settings().SYSTEM_API_KEY})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["exitosos"] == 1 and j["erroneos"] == 0 and j["respuestas"][0]["accion"] == "creado"
    # mal formado: sin respuestas
    r = await client.post("/api/integraciones/forms/respuestas", json={"respuestas": []},
                          headers={"Authorization": get_settings().SYSTEM_API_KEY})
    assert r.status_code == 422
