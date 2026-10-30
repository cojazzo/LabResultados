"""Sugerencias de alumno en la tira (ID con nombre) y unificación con equivalencias explícitas."""
import json
import os
import sys
from datetime import date

import pytest
from sqlalchemy import select

from app.models import Lote, Paciente, Prueba, Resultado
from app.services.tamiz_sync import resolver_folio, sincronizar_alumnos
from app.services.uc1000_parser import process_uc1000_csv
from tests.test_tamiz_integration import alumno, csv_tira, db, valores  # noqa: F401  (db es fixture)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed"))
from unificar_duplicados_folio import unificar  # noqa: E402


@pytest.mark.asyncio
async def test_tira_con_nombre_en_el_id_sugiere_el_alumno_del_padron(db):
    await sincronizar_alumnos(db, [alumno(folio="S26125500", nombres="CARLOS EMMANUEL", primer_apellido="ALONSO",
                                          segundo_apellido="AGUILAR")])
    lote = await process_uc1000_csv(db, csv_tira([("CARLOS EMMANUE", "27/10/2026", "100", "30"),
                                                  ("PERSONA NOEXISTE", "27/10/2026", "100", "30")]), "tira.csv", 1)
    errores = [e["error"] for e in json.loads(lote.log_errores)]
    assert "¿Será S26125500" in errores[0]
    assert "¿Será" not in errores[1]
    assert (await db.execute(select(Resultado))).scalars().all() == []     # solo sugiere, no carga


@pytest.mark.asyncio
async def test_unifica_con_mapa_cualquier_identificacion_syn_y_curp(db):
    await sincronizar_alumnos(db, [alumno(folio="S26137497", nombres="AXEL DAVID", primer_apellido="GARCIA",
                                          segundo_apellido="GOMEZ")])
    real = await resolver_folio(db, "S26137497")
    syn = Paciente(identificacion="SYN-667C96C525FB82", nombre="AXEL DAVID", apellido="GARCIA GOMEZ",
                   origen="servicio_externo")
    db.add(syn)
    await db.flush()
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    db.add(lote)
    await db.flush()
    cre = Prueba(codigo="CRE01", nombre="Creatinina Urinaria", categoria="Orina", unidad="mg/dL")
    db.add(cre)
    await db.flush()
    db.add(Resultado(lote_id=lote.id, paciente_id=syn.id, prueba_id=cre.id, valor=150, interpretacion="normal",
                     fecha_toma=date(2026, 10, 26), fecha_resultado=date(2026, 10, 26), fuente="vitros"))
    await db.commit()

    cuenta, _ = await unificar(db, imprimir=lambda *_: None,
                               mapa={"SYN-667C96C525FB82": "S26137497", "SYN-NOEXISTE": "S26137497"})
    await db.commit()
    assert cuenta["pacientes unificados"] == 1
    assert {p.id for p in (await db.execute(select(Paciente))).scalars().all()} == {real.id}
    assert (await valores(db, real.id))[("CRE01", date(2026, 10, 19))] == (150.0, "vitros")


@pytest.mark.asyncio
async def test_unifica_un_paciente_externo_con_curp_con_su_duplicado_numerico(db):
    """El destino también puede ser la CURP de un paciente que no es del padrón."""
    curp = "ROSR560328HASSRM01"
    destino = Paciente(identificacion=curp, nombre="RAMON", apellido="DE LA ROSA", origen="servicio_externo")
    dup = Paciente(identificacion="99921729", nombre="RAMON", apellido="DE LA ROSA", origen="servicio_externo")
    db.add_all([destino, dup])
    await db.flush()
    lote = Lote(nombre="v.xls", descripcion="t", usuario_id=1, estado="procesando",
                total_registros=0, registros_exitosos=0, registros_error=0)
    cre = Prueba(codigo="CRE01", nombre="Creatinina Urinaria", categoria="Orina", unidad="mg/dL")
    db.add_all([lote, cre])
    await db.flush()
    db.add(Resultado(lote_id=lote.id, paciente_id=destino.id, prueba_id=cre.id, valor=200, interpretacion="normal",
                     fecha_toma=date(2026, 10, 23), fecha_resultado=date(2026, 10, 23), fuente="tira_uc1000"))
    db.add(Resultado(lote_id=lote.id, paciente_id=dup.id, prueba_id=cre.id, valor=231.2, interpretacion="normal",
                     fecha_toma=date(2026, 10, 27), fecha_resultado=date(2026, 10, 27), fuente="vitros"))
    await db.commit()

    cuenta, _ = await unificar(db, imprimir=lambda *_: None, mapa={"99921729": curp})
    await db.commit()
    assert cuenta["pacientes unificados"] == 1 and cuenta["Vitros reemplaza a tira"] == 1
    assert await valores(db, destino.id) == {("CRE01", date(2026, 10, 23)): (231.2, "vitros")}
