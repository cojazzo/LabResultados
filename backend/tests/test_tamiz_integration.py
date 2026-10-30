"""
Pruebas de la integración con tamiz-escolar.
Todos los datos son ficticios (folios, CURP y nombres inventados).
"""
import csv
import io
import json
from datetime import date

import pandas as pd
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, Campana, CampanaPaciente, Lote, Paciente, Prueba, ReporteGenerado, ReporteResultado, Resultado, User,
)
from app.services.excel_parser import process_horizontal_excel
from app.services.tamiz_sync import (
    fecha_toma_tamiz, normalizar_folio, resolver_folio, sincronizar_alumnos,
)
from app.services.uc1000_parser import process_uc1000_csv

CURP_A = "TEST010101HASAAA01"
CURP_B = "TEST020202MASBBB02"


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool,
                                 connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        session.add(User(username="u", email="u@x.mx", hashed_password="x", nombre_completo="U"))
        await session.commit()
        yield session
    await engine.dispose()


def alumno(folio="S00000001", curp=CURP_A, **extra):
    base = {"folio": folio, "curp": curp, "nombres": "ANA", "primer_apellido": "PRUEBA",
            "segundo_apellido": "UNO", "fecha_nacimiento": "2011-03-05", "sexo": "H",
            "cct": "01DES0000X", "escuela": "SECUNDARIA DE PRUEBA", "turno": "MATUTINO",
            "grado": 3, "grupo": "A", "ronda": 1, "fecha_evaluacion": "2026-10-19"}
    base.update(extra)
    return base


def csv_tira(filas):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["UC-1000 DATA"] + [""] * 80)
    w.writerow(["Version", "Id"] + [""] * 79)
    for id_, fecha, cre, alb in filas:
        row = [""] * 81
        row[1], row[8], row[74], row[80] = id_, fecha, cre, alb
        w.writerow(row)
    return out.getvalue().encode("utf-8")


async def valores(db, paciente_id):
    res = await db.execute(select(Resultado, Prueba).join(Prueba, Prueba.id == Resultado.prueba_id)
                           .where(Resultado.paciente_id == paciente_id))
    return {(p.codigo, r.fecha_toma): (float(r.valor), r.fuente) for r, p in res.all() if r.valor is not None}


# ---------------------------------------------------------------------------

def test_normalizar_folio():
    assert normalizar_folio("S26136937") == "S26136937"
    assert normalizar_folio(" s26136937 ") == "S26136937"
    assert normalizar_folio("17S26136937") == "S26136937"      # con modificador del UC-1000
    assert normalizar_folio("1799921732") is None               # ID de petición del servicio externo
    assert normalizar_folio("99921732") is None
    assert normalizar_folio(None) is None
    assert normalizar_folio("S2613693") is None


@pytest.mark.asyncio
async def test_sincronizar_crea_inscribe_y_es_idempotente(db):
    r1 = await sincronizar_alumnos(db, [alumno()])
    assert r1["creados"] == 1 and r1["inscritos_nuevos"] == 1 and not r1["conflictos"]

    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == CURP_A and p.origen == "secundaria" and p.apellido == "PRUEBA"
    camp = (await db.execute(select(Campana))).scalar_one()
    assert camp.slug == "secundarias-2026-2027" and camp.tipo == "secundaria"
    cp = (await db.execute(select(CampanaPaciente))).scalar_one()
    ctx = json.loads(cp.datos_contextuales)
    assert ctx["cct"] == "01DES0000X" and ctx["fecha_evaluacion"] == "2026-10-19"

    r2 = await sincronizar_alumnos(db, [alumno()])
    assert r2["creados"] == 0 and r2["sin_cambios"] == 1 and r2["inscritos_nuevos"] == 0
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_alumno_sin_curp_usa_folio_y_despues_recibe_curp(db):
    await sincronizar_alumnos(db, [alumno(curp=None)])
    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == "TAMIZ-S00000001"

    r = await sincronizar_alumnos(db, [alumno(curp=CURP_A)])
    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == CURP_A and r["curp_asignada"] == 1
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_paciente_existente_por_curp_recibe_el_folio(db):
    db.add(Paciente(identificacion=CURP_A, nombre="ANA", apellido="PRUEBA", origen="servicio_externo"))
    await db.flush()
    r = await sincronizar_alumnos(db, [alumno()])
    assert r["creados"] == 0 and r["actualizados"] == 1
    p = await resolver_folio(db, "S00000001")
    assert p.identificacion == CURP_A and p.origen == "secundaria"
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_misma_curp_en_dos_folios_es_conflicto(db):
    r = await sincronizar_alumnos(db, [alumno("S00000001", CURP_A), alumno("S00000002", CURP_A)])
    assert r["creados"] == 1 and len(r["conflictos"]) == 1
    assert await resolver_folio(db, "S00000002") is None


@pytest.mark.asyncio
async def test_sexo_se_convierte_de_tamiz_a_lab(db):
    """Tamiz usa la convención de la CURP (H = hombre, M = mujer); LabResultados usa M/F."""
    r = await sincronizar_alumnos(db, [alumno("S00000001", CURP_A, sexo="H"),
                                       alumno("S00000002", CURP_B, sexo="M")])
    assert not r["conflictos"]
    assert (await resolver_folio(db, "S00000001")).sexo == "M"   # hombre
    assert (await resolver_folio(db, "S00000002")).sexo == "F"   # mujer


@pytest.mark.asyncio
async def test_sexo_que_no_coincide_con_la_curp_se_reporta(db):
    r = await sincronizar_alumnos(db, [alumno("S00000001", CURP_A, sexo="M")])   # CURP dice H
    assert r["creados"] == 1
    assert any("sexo" in c["motivo"] for c in r["conflictos"])


@pytest.mark.asyncio
async def test_alumno_sin_apellido_paterno_usa_el_materno(db):
    r = await sincronizar_alumnos(db, [alumno(primer_apellido=None, segundo_apellido="UNICO")])
    assert r["creados"] == 1
    assert (await resolver_folio(db, "S00000001")).apellido == "UNICO"


@pytest.mark.asyncio
async def test_regla_de_fecha_de_toma(db):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")
    # 1a muestra: fecha de evaluación aunque el archivo traiga otra fecha
    assert await fecha_toma_tamiz(db, p, date(2026, 10, 24)) == date(2026, 10, 19)
    assert await fecha_toma_tamiz(db, p, None) == date(2026, 10, 19)
    # 2a muestra (ventana 07-ene-2027 en adelante): fecha del archivo
    assert await fecha_toma_tamiz(db, p, date(2027, 1, 12)) == date(2027, 1, 12)
    # alumno sin evaluación capturada: fecha del archivo
    await sincronizar_alumnos(db, [alumno("S00000002", CURP_B, fecha_evaluacion=None)])
    q = await resolver_folio(db, "S00000002")
    assert await fecha_toma_tamiz(db, q, date(2026, 10, 24)) == date(2026, 10, 24)


@pytest.mark.asyncio
async def test_tira_y_vitros_por_folio_caen_en_la_misma_visita(db):
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")

    # 1) tira (procesada 3 días después de la evaluación): ALB 30, CRE 150 -> ACR 20
    lote = await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "150", "30")]), "tira.csv", 1)
    assert lote.registros_exitosos == 1 and lote.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))] == (150.0, "tira_uc1000")
    assert v[("ALBOR", date(2026, 10, 19))] == (30.0, "tira_uc1000")
    assert v[("ACR", date(2026, 10, 19))][0] == pytest.approx(20.0)

    # 2) Vitros confirma la creatinina (otra fecha de proceso): reemplaza a la tira y recalcula el ACR
    lote2 = Lote(nombre="vitros.xlsx", descripcion="t", usuario_id=1, estado="procesando",
                 total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote2)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-26", "Número": "S00000001", "Nombre del Paciente": None,
                        "Apellidos": None, "NTS": None, "CRE01": "120"}])
    lote2 = await process_horizontal_excel(db, df, lote2)
    assert lote2.registros_exitosos == 1 and lote2.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))] == (120.0, "vitros")
    assert v[("ACR", date(2026, 10, 19))][0] == pytest.approx(25.0)
    assert not any(f != date(2026, 10, 19) for (_, f) in v)          # una sola visita
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1   # no se crearon pacientes por nombre


@pytest.mark.asyncio
async def test_folio_desconocido_da_error_y_no_crea_pacientes(db):
    lote = await process_uc1000_csv(db, csv_tira([("S99999999", "22/10/2026", "100", "10")]), "tira.csv", 1)
    assert lote.registros_error == 1 and "S99999999" in lote.log_errores

    lote2 = Lote(nombre="v.xlsx", descripcion="t", usuario_id=1, estado="procesando",
                 total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote2)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-26", "Número": "S99999999", "Nombre del Paciente": "X",
                        "Apellidos": "Y", "NTS": None, "CRE01": "100"}])
    lote2 = await process_horizontal_excel(db, df, lote2)
    assert lote2.registros_error == 1
    assert (await db.execute(select(Paciente))).scalars().all() == []


@pytest.mark.asyncio
async def test_servicio_externo_sigue_resolviendo_por_peticion(db):
    """Regresión: el ID 17 + petición del servicio externo no cambia."""
    p = Paciente(identificacion="SYN-TEST", nombre="EXTERNO", apellido="PRUEBA")
    db.add(p)
    await db.flush()
    lote = Lote(nombre="v.xlsx", descripcion="t", usuario_id=1, estado="completado",
                total_registros=1, registros_exitosos=1, registros_error=0)
    db.add(lote)
    await db.flush()
    pr = Prueba(codigo="CRTS", nombre="CRTS", categoria="Química Clínica", unidad="", activa=True)
    db.add(pr)
    await db.flush()
    db.add(Resultado(lote_id=lote.id, paciente_id=p.id, prueba_id=pr.id, valor=0.8,
                     fecha_toma=date(2026, 9, 18), fecha_resultado=date(2026, 9, 18),
                     observaciones="Petición No. 99921732", fuente="vitros", interpretacion="normal"))
    await db.flush()

    res = await process_uc1000_csv(db, csv_tira([("1799921732", "18/09/2026", "100", "10")]), "tira.csv", 1)
    assert res.registros_exitosos == 1 and res.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 9, 18))] == (100.0, "tira_uc1000")


@pytest.mark.asyncio
async def test_realinea_fechas_cuando_llega_la_evaluacion_despues(db):
    # llega el alumno sin evaluación capturada y se carga una tira con la fecha del archivo
    await sincronizar_alumnos(db, [alumno(fecha_evaluacion=None)])
    p = await resolver_folio(db, "S00000001")
    await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "100", "10")]), "tira.csv", 1)
    assert all(f == date(2026, 10, 22) for (_, f) in await valores(db, p.id))

    # después se captura la evaluación (19-oct): los resultados de la 1a muestra se mueven a esa fecha
    r = await sincronizar_alumnos(db, [alumno(fecha_evaluacion="2026-10-19")])
    assert r["fechas_realineadas"] == 3 and r["fechas_en_conflicto"] == 0
    assert all(f == date(2026, 10, 19) for (_, f) in await valores(db, p.id))


@pytest.mark.asyncio
async def test_endpoint_requiere_autenticacion_y_acepta_clave_de_sistema(client):
    from app.config import get_settings
    body = {"campana": {"ciclo": "2026-2027"}, "alumnos": [alumno("S00000077", "TEST030303HASCCC03")]}
    assert (await client.post("/api/integraciones/tamiz/alumnos", json=body)).status_code == 401
    r = await client.post("/api/integraciones/tamiz/alumnos", json=body,
                          headers={"Authorization": get_settings().SYSTEM_API_KEY})
    assert r.status_code == 200, r.text
    assert r.json()["creados"] + r.json()["actualizados"] + r.json()["sin_cambios"] == 1


@pytest.mark.asyncio
async def test_listado_de_pacientes_paginado_y_buscable_por_folio(client, auth_headers):
    from app.config import get_settings
    alumnos = [alumno(f"S9000000{i}", f"TEST0{i}0{i}0{i}HASDDD0{i}") for i in range(1, 4)]
    r = await client.post("/api/integraciones/tamiz/alumnos", json={"alumnos": alumnos},
                          headers={"Authorization": get_settings().SYSTEM_API_KEY})
    assert r.status_code == 200, r.text

    r = await client.get("/api/pacientes", params={"search": "S9000000", "limit": 2}, headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["x-total-count"] == "3"
    assert len(r.json()) == 2 and r.json()[0]["folio_tamiz"].startswith("S9000000")

    r = await client.get("/api/pacientes", params={"search": "S90000002"}, headers=auth_headers)
    assert r.headers["x-total-count"] == "1"


@pytest.mark.asyncio
async def test_vitros_con_folio_en_nts_se_resuelve_por_folio(db):
    """En los Excel de Vitros de las escuelas el folio viene en NTS (y Número es otro identificador)."""
    await sincronizar_alumnos(db, [alumno()])
    p = await resolver_folio(db, "S00000001")
    lote = Lote(nombre="vitros.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    df = pd.DataFrame([{"Fecha": "2026-10-27", "Número": "99921800", "Nombre del Paciente": "ANA",
                        "Apellidos": "PRUEBA UNO", "NTS": "S00000001", "CRE01": "120", "ALBOR": "30"}])
    lote = await process_horizontal_excel(db, df, lote)
    assert lote.registros_exitosos == 1 and lote.registros_error == 0
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))] == (120.0, "vitros")
    assert len((await db.execute(select(Paciente))).scalars().all()) == 1     # sin paciente duplicado


@pytest.mark.asyncio
async def test_unifica_duplicado_creado_con_folio_como_identificacion(db):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
    from unificar_duplicados_folio import unificar

    await sincronizar_alumnos(db, [alumno()])
    real = await resolver_folio(db, "S00000001")
    # tira ya cargada en el paciente del padrón: ALB 30, CRE 150 -> ACR 20
    await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "150", "30")]), "tira.csv", 1)

    # duplicado como lo dejaba la carga vieja: identificacion = folio, fecha del archivo, CRE de Vitros
    dup = Paciente(identificacion="S00000001", nombre="ANA", apellido="PRUEBA UNO", origen="servicio_externo")
    db.add(dup)
    await db.flush()
    lote = Lote(nombre="vitros.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    crtn = (await db.execute(select(Prueba).where(Prueba.codigo == "CRE01"))).scalar_one()
    res_dup = Resultado(lote_id=lote.id, paciente_id=dup.id, prueba_id=crtn.id, valor=120, interpretacion="normal",
                        fecha_toma=date(2026, 10, 27), fecha_resultado=date(2026, 10, 27), fuente="vitros")
    db.add(res_dup)
    await db.flush()
    rep = ReporteGenerado(paciente_id=dup.id, lote_id=lote.id, folio="REP-T-1", ruta_archivo="x.pdf")
    db.add(rep)
    await db.flush()
    db.add(ReporteResultado(reporte_id=rep.id, resultado_id=res_dup.id))
    await db.commit()

    cuenta, _ = await unificar(db, imprimir=lambda *_: None)
    await db.commit()
    assert cuenta["pacientes unificados"] == 1 and cuenta["Vitros reemplaza a tira"] == 1

    pacientes = (await db.execute(select(Paciente))).scalars().all()
    assert [p.id for p in pacientes] == [real.id]
    v = await valores(db, real.id)
    assert v[("CRE01", date(2026, 10, 19))] == (120.0, "vitros")
    assert v[("ALBOR", date(2026, 10, 19))] == (30.0, "tira_uc1000")
    assert v[("ACR", date(2026, 10, 19))][0] == pytest.approx(25.0)
    assert not any(f != date(2026, 10, 19) for (_, f) in v)
    # el reporte ya generado pasó al paciente del padrón y apunta a un resultado que existe
    await db.refresh(rep)
    assert rep.paciente_id == real.id
    rr = (await db.execute(select(ReporteResultado).where(ReporteResultado.reporte_id == rep.id))).scalar_one()
    destino = (await db.execute(select(Resultado).where(Resultado.id == rr.resultado_id))).scalar_one()
    assert destino.paciente_id == real.id and destino.fuente == "vitros"


@pytest.mark.asyncio
async def test_folio_desconocido_sugiere_el_del_padron(db):
    await sincronizar_alumnos(db, [alumno(folio="S26008185", nombres="RAUL FERNANDO", primer_apellido="AVILA",
                                          segundo_apellido="MUÑOZ"),
                                   alumno(folio="S26127258", curp=CURP_B, nombres="DYLAN ALEXANDER",
                                          primer_apellido="REYES", segundo_apellido="MEDINA")])

    def excel(fila):
        return pd.DataFrame([{"Fecha": "2026-10-26", "Número": "99921800", "NTS": fila[0],
                              "Nombre del Paciente": fila[1], "Apellidos": fila[2], "CRE01": "120"}])

    def msg(lote):
        return " ".join(e["error"] for e in json.loads(lote.log_errores))

    async def subir(df):
        lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                    total_registros=0, registros_exitosos=0, registros_error=0)
        db.add(lote)
        await db.flush()
        return await process_horizontal_excel(db, df, lote)

    # un dígito mal y mismo nombre (con acento distinto) -> sugiere
    l1 = await subir(excel(("S26006185", "Raul Fernando", "Avila Muñoz")))
    assert l1.registros_error == 1 and "¿Quisiste decir S26008185?" in msg(l1)
    # un dígito mal y el nombre también tiene un error de captura -> sugiere
    l2 = await subir(excel(("S26127256", "DYLAN ALEXANER", "REYES MEDINA")))
    assert "S26127258" in msg(l2)
    # mismo nombre pero folio totalmente distinto (cambió de escuela) -> sugiere por nombre
    l3 = await subir(excel(("S26999999", "RAUL FERNANDO", "AVILA MUÑOZ")))
    assert "S26008185" in msg(l3) and "mismo nombre" in msg(l3)
    # nombre que no corresponde a nadie -> sin sugerencia, y nunca se crean pacientes
    l4 = await subir(excel(("S26006185", "PERSONA", "INVENTADA")))
    assert "Quisiste decir" not in msg(l4)
    assert len((await db.execute(select(Paciente))).scalars().all()) == 2


@pytest.mark.asyncio
async def test_unifica_folio_mal_capturado_con_mapa_explicito(db):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
    from unificar_duplicados_folio import unificar

    await sincronizar_alumnos(db, [alumno(folio="S26008185")])
    real = await resolver_folio(db, "S26008185")
    mal = Paciente(identificacion="S26006185", nombre="ANA", apellido="PRUEBA UNO", origen="servicio_externo")
    otro = Paciente(identificacion="S26555555", nombre="OTRA", apellido="PERSONA", origen="servicio_externo")
    db.add_all([mal, otro])
    await db.flush()
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    cre = Prueba(codigo="CRE01", nombre="Creatinina Urinaria", categoria="Orina", unidad="mg/dL")
    db.add(cre)
    await db.flush()
    db.add(Resultado(lote_id=lote.id, paciente_id=mal.id, prueba_id=cre.id, valor=125, interpretacion="normal",
                     fecha_toma=date(2026, 10, 27), fecha_resultado=date(2026, 10, 27), fuente="vitros"))
    await db.commit()

    # sin mapa no se une (el folio mal capturado no existe en el padrón)
    cuenta, _ = await unificar(db, imprimir=lambda *_: None)
    assert cuenta["pacientes unificados"] == 0
    # con mapa solo se une el indicado; el otro folio queda intacto
    cuenta, _ = await unificar(db, imprimir=lambda *_: None, mapa={"S26006185": "S26008185"})
    await db.commit()
    assert cuenta["pacientes unificados"] == 1
    ids = {p.identificacion for p in (await db.execute(select(Paciente))).scalars().all()}
    assert ids == {CURP_A, "S26555555"}
    v = await valores(db, real.id)
    assert v[("CRE01", date(2026, 10, 19))] == (125.0, "vitros")


@pytest.mark.asyncio
async def test_vitros_por_curp_cae_en_la_visita_de_evaluacion_y_se_reunen_las_ya_separadas(db):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
    from reunir_visitas_tamiz import reunir

    await sincronizar_alumnos(db, [alumno()])          # evaluación 2026-10-19
    p = await resolver_folio(db, "S00000001")
    await process_uc1000_csv(db, csv_tira([("S00000001", "22/10/2026", "100", "30")]), "tira.csv", 1)

    df = pd.DataFrame([{"Fecha": "2026-10-28", "Número": "99921800", "Nombre del Paciente": "OTRO NOMBRE",
                        "Apellidos": "OTRO APELLIDO", "NTS": CURP_A, "CRE01": "132.3"}])
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    # el alumno viene identificado por CURP: antes caía en la fecha del archivo (28) y no se juntaba con la tira
    await process_horizontal_excel(db, df, lote)
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))] == (132.3, "vitros")
    assert v[("ACR", date(2026, 10, 19))][0] == pytest.approx(30 / 132.3 * 100, rel=1e-3)
    assert not any(f != date(2026, 10, 19) for (_, f) in v)
    pac = (await db.execute(select(Paciente))).scalar_one()
    assert (pac.nombre, pac.apellido) == ("ANA", "PRUEBA")           # tamiz manda los datos, no el Excel

    # datos ya cargados en visitas separadas (como quedaron antes del arreglo) -> el script los reúne
    for r in (await db.execute(select(Resultado).join(Prueba, Prueba.id == Resultado.prueba_id)
                               .where(Prueba.codigo == "CRE01", Resultado.fuente == "vitros"))).scalars():
        r.fecha_toma = date(2026, 10, 28)
    await db.commit()
    cuenta, _ = await reunir(db)
    await db.commit()
    assert cuenta["alumnos reunidos"] == 1
    v = await valores(db, p.id)
    assert v[("CRE01", date(2026, 10, 19))][1] in ("vitros", "tira_uc1000")
    assert not any(f != date(2026, 10, 19) for (_, f) in v)


@pytest.mark.asyncio
async def test_alumno_sin_evaluacion_une_tira_y_vitros_de_la_misma_toma(db):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
    from reunir_visitas_tamiz import reunir

    await sincronizar_alumnos(db, [alumno(fecha_evaluacion=None)])      # tamiz aún no captura la evaluación
    p = await resolver_folio(db, "S00000001")
    await process_uc1000_csv(db, csv_tira([("S00000001", "27/10/2026", "100", "30")]), "tira.csv", 1)

    df = pd.DataFrame([{"Fecha": "2026-10-28", "Número": "99921800", "Nombre del Paciente": "ANA",
                        "Apellidos": "PRUEBA UNO", "NTS": CURP_A, "CRE01": "132.3"}])
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    await process_horizontal_excel(db, df, lote)
    v = await valores(db, p.id)
    assert not any(f != date(2026, 10, 27) for (_, f) in v)             # una sola visita: la de la primera medición
    assert v[("CRE01", date(2026, 10, 27))] == (132.3, "vitros")
    assert v[("ACR", date(2026, 10, 27))][0] == pytest.approx(30 / 132.3 * 100, rel=1e-3)

    # una segunda muestra meses después sigue siendo su propia visita
    await process_uc1000_csv(db, csv_tira([("S00000001", "15/01/2027", "100", "10")]), "tira2.csv", 1)
    v = await valores(db, p.id)
    assert ("ALBOR", date(2027, 1, 15)) in v and ("ALBOR", date(2026, 10, 27)) in v

    # y las visitas que ya estaban separadas se reúnen con el script
    for r in (await db.execute(select(Resultado).join(Prueba, Prueba.id == Resultado.prueba_id)
                               .where(Prueba.codigo == "CRE01", Resultado.fuente == "vitros"))).scalars():
        r.fecha_toma = date(2026, 10, 28)
    await db.commit()
    cuenta, _ = await reunir(db)
    await db.commit()
    assert cuenta["alumnos reunidos"] == 1
    v = await valores(db, p.id)
    assert ("CRE01", date(2026, 10, 27)) in v and ("CRE01", date(2026, 10, 28)) not in v
