"""
Parser especializado para el formato de Excel de secundarias.

Columnas esperadas del Excel:
- CURP_ALUMNO       → paciente.identificacion
- NOM_ALUMNO        → paciente.nombre
- P_APELLIDO_ALUMNO → paciente.apellido
- S_APELLIDO_ALUMNO → paciente.apellido_materno
- Edad_Alumno       → referencia (edad no se almacena, se calcula de CURP)
- Direccion_Alumno  → paciente.domicilio
- Telefono_Alumno   → paciente.telefono
- NombreCT          → datos_contextuales.secundaria
- DireccionCT       → datos_contextuales.direccion_escuela
- Turno             → datos_contextuales.turno
- CCT               → datos_contextuales.cct
"""
import io
import json
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Lote, Paciente, CampanaPaciente, Campana
from app.utils.curp_validator import match_patient_identifier


async def process_secundaria_excel(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    usuario_id: int,
    campana_id: int,
) -> dict:
    """
    Procesa un Excel con la base de datos de alumnos de secundaria.
    Crea/actualiza pacientes con origen='secundaria' y los asocia a la campaña.
    Guarda datos contextuales (secundaria, turno, dirección de la escuela).
    """
    # 1. Verificar que la campaña existe y es de tipo secundaria
    campana_res = await db.execute(select(Campana).where(Campana.id == campana_id))
    campana = campana_res.scalar_one_or_none()
    if not campana:
        raise ValueError(f"Campaña con ID {campana_id} no encontrada")
    if campana.tipo != "secundaria":
        raise ValueError(f"La campaña '{campana.nombre}' no es de tipo secundaria")

    # 2. Crear el lote
    lote = Lote(
        nombre=filename,
        descripcion=f"Carga de alumnos de secundaria - {campana.nombre}",
        usuario_id=usuario_id,
        estado="procesando",
        total_registros=0,
        registros_exitosos=0,
        registros_error=0,
    )
    db.add(lote)
    await db.commit()
    await db.refresh(lote)

    errors = []
    exitosos = 0
    erroneos = 0
    inscritos_campana = 0

    # 3. Leer Excel
    try:
        df = pd.read_excel(io.BytesIO(file_content), keep_default_na=False)
        df = df.replace("", None)
    except Exception as e:
        lote.estado = "error"
        lote.log_errores = json.dumps([{
            "fila": 0, "columna": "archivo",
            "error": f"No se pudo leer el archivo: {str(e)}", "valor": ""
        }])
        await db.commit()
        return {"lote": lote, "inscritos_campana": 0}

    total_filas = len(df)
    if total_filas == 0:
        lote.estado = "error"
        lote.log_errores = json.dumps([{
            "fila": 0, "columna": "archivo",
            "error": "El archivo Excel está vacío", "valor": ""
        }])
        await db.commit()
        return {"lote": lote, "inscritos_campana": 0}

    # 4. Mapear columnas (tolerante a variaciones)
    col_map = {}
    for col in df.columns:
        col_lower = col.strip().lower().replace(" ", "_")
        col_map[col_lower] = col

    def get_col(alternatives):
        for alt in alternatives:
            if alt in col_map:
                return col_map[alt]
        return None

    curp_col = get_col(["curp_alumno", "curp"])
    nombre_col = get_col(["nom_alumno", "nombre_alumno", "nombre"])
    ap_pat_col = get_col(["p_apellido_alumno", "apellido_paterno", "primer_apellido"])
    ap_mat_col = get_col(["s_apellido_alumno", "apellido_materno", "segundo_apellido"])
    edad_col = get_col(["edad_alumno", "edad"])
    dir_alumno_col = get_col(["direccion_alumno", "domicilio_alumno", "domicilio"])
    tel_col = get_col(["telefono_alumno", "telefono"])
    escuela_col = get_col(["nombrect", "nombre_escuela", "escuela", "centro_trabajo"])
    dir_escuela_col = get_col(["direccionct", "direccion_escuela", "dir_escuela"])
    turno_col = get_col(["turno"])
    cct_col = get_col(["cct", "clave_centro_trabajo"])

    if not curp_col:
        lote.estado = "error"
        lote.log_errores = json.dumps([{
            "fila": 0, "columna": "CURP_ALUMNO",
            "error": "No se encontró la columna CURP_ALUMNO en el archivo", "valor": ""
        }])
        await db.commit()
        return {"lote": lote, "inscritos_campana": 0}

    # 5. Procesar filas
    for index, row in df.iterrows():
        fila_num = index + 2  # +2 por header y 0-index

        # Extraer CURP
        curp_raw = str(row[curp_col]).strip().upper() if pd.notna(row[curp_col]) else ""
        if not curp_raw or curp_raw == "NAN" or curp_raw == "NONE":
            # Fila vacía, saltar sin contar como error
            continue

        nombre = str(row[nombre_col]).strip() if nombre_col and pd.notna(row[nombre_col]) else ""
        ap_pat = str(row[ap_pat_col]).strip() if ap_pat_col and pd.notna(row[ap_pat_col]) else ""
        ap_mat = str(row[ap_mat_col]).strip() if ap_mat_col and pd.notna(row[ap_mat_col]) else ""

        if not nombre and not ap_pat:
            erroneos += 1
            errors.append({
                "fila": fila_num, "columna": "nombre",
                "error": "Falta nombre y apellido", "valor": curp_raw
            })
            continue

        # Identificador del paciente
        identificador = match_patient_identifier(curp_raw, nombre, ap_pat)
        if not identificador:
            identificador = curp_raw

        # Buscar/crear paciente
        pac_res = await db.execute(
            select(Paciente).where(Paciente.identificacion == identificador)
        )
        paciente = pac_res.scalar_one_or_none()

        telefono = str(row[tel_col]).strip() if tel_col and pd.notna(row[tel_col]) else None
        domicilio = str(row[dir_alumno_col]).strip() if dir_alumno_col and pd.notna(row[dir_alumno_col]) else None

        # Inferir sexo de CURP (posición 10: M=mujer, H=hombre)
        sexo = None
        if len(curp_raw) >= 11:
            char = curp_raw[10]
            if char == "M":
                sexo = "F"
            elif char == "H":
                sexo = "M"

        if not paciente:
            paciente = Paciente(
                identificacion=identificador,
                nombre=nombre,
                apellido=ap_pat,
                apellido_materno=ap_mat if ap_mat else None,
                sexo=sexo,
                telefono=telefono,
                domicilio=domicilio,
                origen="secundaria",
            )
            db.add(paciente)
            await db.flush()  # Para obtener el ID
        else:
            # Actualizar datos si los nuevos son más completos
            if nombre and not paciente.nombre:
                paciente.nombre = nombre
            if ap_pat and not paciente.apellido:
                paciente.apellido = ap_pat
            if ap_mat and not paciente.apellido_materno:
                paciente.apellido_materno = ap_mat
            if sexo and not paciente.sexo:
                paciente.sexo = sexo
            if telefono and not paciente.telefono:
                paciente.telefono = telefono
            if domicilio and not paciente.domicilio:
                paciente.domicilio = domicilio
            # Actualizar origen solo si no tenía uno
            if not paciente.origen:
                paciente.origen = "secundaria"

        # Datos contextuales de la escuela
        contexto = {}
        if escuela_col and pd.notna(row[escuela_col]):
            contexto["secundaria"] = str(row[escuela_col]).strip()
        if turno_col and pd.notna(row[turno_col]):
            contexto["turno"] = str(row[turno_col]).strip()
        if dir_escuela_col and pd.notna(row[dir_escuela_col]):
            contexto["direccion_escuela"] = str(row[dir_escuela_col]).strip()
        if cct_col and pd.notna(row[cct_col]):
            contexto["cct"] = str(row[cct_col]).strip()

        # Inscribir en la campaña (si no está ya inscrito)
        existing_cp = await db.execute(
            select(CampanaPaciente).where(
                CampanaPaciente.campana_id == campana_id,
                CampanaPaciente.paciente_id == paciente.id,
            )
        )
        if not existing_cp.scalar_one_or_none():
            cp = CampanaPaciente(
                campana_id=campana_id,
                paciente_id=paciente.id,
                fuente_registro="excel_escuela",
                datos_contextuales=json.dumps(contexto) if contexto else None,
            )
            db.add(cp)
            inscritos_campana += 1

        exitosos += 1

    # 6. Actualizar lote
    lote.total_registros = total_filas
    lote.registros_exitosos = exitosos
    lote.registros_error = erroneos

    if erroneos == 0 and exitosos > 0:
        lote.estado = "completado"
    elif exitosos == 0:
        lote.estado = "error"
    else:
        lote.estado = "error_parcial"

    if errors:
        lote.log_errores = json.dumps(errors)

    await db.commit()
    await db.refresh(lote)

    return {
        "lote": lote,
        "inscritos_campana": inscritos_campana,
        "resumen": {
            "exitosos": exitosos,
            "erroneos": erroneos,
            "total": total_filas,
        }
    }
