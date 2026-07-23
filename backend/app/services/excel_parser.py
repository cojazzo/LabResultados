import io
import json
import pandas as pd
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Lote, Paciente, Prueba, Resultado
from app.utils.validators import normalize_column_name, parse_date, validate_email, calcular_interpretacion
from app.utils.curp_validator import match_patient_identifier

async def process_excel_file(db: AsyncSession, file_content: bytes, filename: str, usuario_id: int) -> Lote:
    """
    Lee y valida un archivo Excel, creando pacientes, médicos y resultados.
    Registra estadísticas de carga y log de errores.
    Soporta formato vertical (resultados individuales) y formato horizontal (visitas con columnas de estudio).
    """
    # 1. Crear el lote con estado inicial "procesando"
    lote = Lote(
        nombre=filename,
        descripcion=f"Carga de archivo Excel {filename}",
        usuario_id=usuario_id,
        estado="procesando",
        total_registros=0,
        registros_exitosos=0,
        registros_error=0,
        log_errores=None
    )
    db.add(lote)
    await db.commit()
    await db.refresh(lote)

    errors = []
    exitosos = 0
    erroneos = 0

    try:
        # Leer Excel con pandas, evitando tratar "NA" (Sodio) como missing value
        df = pd.read_excel(io.BytesIO(file_content), keep_default_na=False)
        df = df.replace("", None)
    except Exception as e:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "columna": "archivo", "error": f"No se pudo leer el archivo: {str(e)}", "valor": ""}])
        await db.commit()
        return lote

    total_filas = len(df)
    if total_filas == 0:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "columna": "archivo", "error": "El archivo Excel está vacío", "valor": ""}])
        await db.commit()
        return lote

    # Mapeo de columnas normalizadas
    cols = {normalize_column_name(col): col for col in df.columns}
    
    # Auto-detectar si es el formato de visita horizontal de otro sistema
    is_horizontal = ("nts" in cols or "sexo_del_paciente" in cols or "edad_del_paciente" in cols)
    if is_horizontal:
        return await process_horizontal_excel(db, df, lote)

    # Mapeo esperado (formato vertical estándar)
    expected_mappings = {
        "identificacion_paciente": ["identificacion_paciente", "identificacion", "paciente_identificacion", "id_paciente"],
        "nombre_paciente": ["nombre_paciente", "nombre", "paciente_nombre"],
        "apellido_paciente": ["apellido_paciente", "apellido", "paciente_apellido"],
        "fecha_nacimiento": ["fecha_nacimiento", "nacimiento", "paciente_fecha_nacimiento"],
        "sexo": ["sexo", "genero", "paciente_sexo"],
        "telefono_paciente": ["telefono_paciente", "telefono", "paciente_telefono"],
        "email_paciente": ["email_paciente", "email", "paciente_email"],
        "whatsapp_paciente": ["whatsapp_paciente", "whatsapp", "paciente_whatsapp"],

        "codigo_prueba": ["codigo_prueba", "codigo", "prueba_codigo", "prueba"],
        "valor": ["valor", "resultado", "resultado_valor"],
        "fecha_toma": ["fecha_toma", "toma", "fecha_muestra"],
        "fecha_resultado": ["fecha_resultado", "fecha_analisis", "fecha_reporte"],
        "observaciones": ["observaciones", "notas", "comentarios"],
        "numero": ["numero", "n_mero", "numero_de_peticion", "folio", "peticion"]
    }

    # Resolver columnas
    resolved_cols = {}
    for canonical, alternatives in expected_mappings.items():
        found = False
        for alt in alternatives:
            norm_alt = normalize_column_name(alt)
            if norm_alt in cols:
                resolved_cols[canonical] = cols[norm_alt]
                found = True
                break
        if not found:
            resolved_cols[canonical] = None

    # Validar columnas requeridas
    required_canonicals = [
        "identificacion_paciente", "nombre_paciente", "apellido_paciente",
        "codigo_prueba", "valor", "fecha_toma"
    ]
    missing_required = [req for req in required_canonicals if resolved_cols[req] is None]
    if missing_required:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "columna": "columnas", "error": f"Faltan columnas requeridas: {', '.join(missing_required)}", "valor": ""}])
        await db.commit()
        return lote

    # Cargar catálogo de pruebas en caché de memoria para optimizar
    pruebas_result = await db.execute(select(Prueba))
    pruebas_cache = {p.codigo: p for p in pruebas_result.scalars().all()}

    # Procesar filas
    for index, row in df.iterrows():
        fila_num = index + 2  # 1-indexed plus header row
        fila_errores = []

        # Extraer y limpiar datos de la fila
        paciente_id_val = str(row[resolved_cols["identificacion_paciente"]]).strip() if pd.notna(row[resolved_cols["identificacion_paciente"]]) else ""
        pac_nombre = str(row[resolved_cols["nombre_paciente"]]).strip() if pd.notna(row[resolved_cols["nombre_paciente"]]) else ""
        pac_apellido = str(row[resolved_cols["apellido_paciente"]]).strip() if pd.notna(row[resolved_cols["apellido_paciente"]]) else ""

        prueba_codigo = str(row[resolved_cols["codigo_prueba"]]).strip() if pd.notna(row[resolved_cols["codigo_prueba"]]) else ""
        
        # Aplicar matching lógico
        paciente_id_val = match_patient_identifier(
            paciente_id_val, pac_nombre, pac_apellido,
            # Se extraería el sexo si estuviera, pero para vertical el curp casi siempre basta
            None
        )
        valor_raw = str(row[resolved_cols["valor"]]).strip() if pd.notna(row[resolved_cols["valor"]]) else ""
        fecha_toma_raw = row[resolved_cols["fecha_toma"]]

        # Validaciones de campos requeridos vacíos
        if not paciente_id_val:
            fila_errores.append({"columna": "Identificacion_Paciente", "error": "La identificación del paciente es obligatoria", "valor": ""})
        if not pac_nombre:
            fila_errores.append({"columna": "Nombre_Paciente", "error": "El nombre del paciente es obligatorio", "valor": ""})
        if not pac_apellido:
            fila_errores.append({"columna": "Apellido_Paciente", "error": "El apellido del paciente es obligatorio", "valor": ""})

        if not prueba_codigo:
            fila_errores.append({"columna": "Codigo_Prueba", "error": "El código de la prueba es obligatorio", "valor": ""})
        if not valor_raw:
            fila_errores.append({"columna": "Valor", "error": "El valor del resultado es obligatorio", "valor": ""})

        # Validar formato de fecha de toma
        fecha_toma_val = parse_date(fecha_toma_raw)
        if not fecha_toma_val:
            fila_errores.append({"columna": "Fecha_Toma", "error": "La fecha de toma es obligatoria y debe ser una fecha válida", "valor": str(fecha_toma_raw)})

        # Filtrar solo pruebas de función renal requeridas
        if prueba_codigo.upper() not in ["CRTS", "CRE01", "ALBOR", "ACR"]:
            total_filas -= 1
            continue

        # Validar existencia de la prueba en catálogo
        prueba = pruebas_cache.get(prueba_codigo)
        if not prueba and prueba_codigo:
            fila_errores.append({"columna": "Codigo_Prueba", "error": f"El código de prueba '{prueba_codigo}' no existe en el catálogo", "valor": prueba_codigo})

        if fila_errores:
            for err in fila_errores:
                errors.append({"fila": fila_num, **err})
            erroneos += 1
            continue

        # Procesar Paciente
        paciente_res = await db.execute(select(Paciente).where(Paciente.identificacion == paciente_id_val))
        paciente = paciente_res.scalar_one_or_none()
        
        pac_fn = parse_date(row[resolved_cols["fecha_nacimiento"]]) if resolved_cols["fecha_nacimiento"] else None
        pac_sex = str(row[resolved_cols["sexo"]]).strip() if resolved_cols["sexo"] and pd.notna(row[resolved_cols["sexo"]]) else None
        pac_tel = str(row[resolved_cols["telefono_paciente"]]).strip() if resolved_cols["telefono_paciente"] and pd.notna(row[resolved_cols["telefono_paciente"]]) else None
        pac_mail = str(row[resolved_cols["email_paciente"]]).strip() if resolved_cols["email_paciente"] and pd.notna(row[resolved_cols["email_paciente"]]) else None
        pac_wa = str(row[resolved_cols["whatsapp_paciente"]]).strip() if resolved_cols["whatsapp_paciente"] and pd.notna(row[resolved_cols["whatsapp_paciente"]]) else None

        if not paciente:
            paciente = Paciente(
                identificacion=paciente_id_val,
                nombre=pac_nombre,
                apellido=pac_apellido,
                fecha_nacimiento=pac_fn,
                sexo=pac_sex,
                telefono=pac_tel,
                email=pac_mail,
                whatsapp=pac_wa
            )
            db.add(paciente)
            await db.flush()
        else:
            if pac_nombre: paciente.nombre = pac_nombre
            if pac_apellido: paciente.apellido = pac_apellido
            if pac_fn: paciente.fecha_nacimiento = pac_fn
            if pac_sex: paciente.sexo = pac_sex
            if pac_tel: paciente.telefono = pac_tel
            if pac_mail: paciente.email = pac_mail
            if pac_wa: paciente.whatsapp = pac_wa



        # Parsear Valor y calcular interpretación
        valor_num = None
        valor_text = None
        interpretacion = "normal"
        
        try:
            clean_val = valor_raw.replace(",", ".")
            valor_num = float(clean_val)
            interpretacion = calcular_interpretacion(
                valor_num,
                prueba.valor_min,
                prueba.valor_max,
                prueba.valor_critico_min,
                prueba.valor_critico_max
            )
        except ValueError:
            valor_text = valor_raw
            interpretacion = "normal"

        # Fechas y observaciones adicionales
        fecha_res_val = parse_date(row[resolved_cols["fecha_resultado"]]) if resolved_cols["fecha_resultado"] else None
        
        obs_parts = []
        if resolved_cols["numero"] and pd.notna(row[resolved_cols["numero"]]):
            num_val = str(row[resolved_cols["numero"]]).strip()
            if num_val:
                obs_parts.append(f"Petición No. {num_val}")
        
        if resolved_cols["observaciones"] and pd.notna(row[resolved_cols["observaciones"]]):
            obs_raw = str(row[resolved_cols["observaciones"]]).strip()
            if obs_raw:
                obs_parts.append(obs_raw)
                
        obs_val = " | ".join(obs_parts) if obs_parts else None

        # PREVENCIÓN DE DUPLICADOS
        res_stmt = select(Resultado).where(
            Resultado.paciente_id == paciente.id,
            Resultado.prueba_id == prueba.id,
            Resultado.fecha_toma == fecha_toma_val
        )
        res_query = await db.execute(res_stmt)
        resultado = res_query.scalars().first()

        if resultado:
            resultado.lote_id = lote.id
            resultado.valor = Decimal(str(valor_num)) if valor_num is not None else None
            resultado.valor_texto = valor_text
            resultado.interpretacion = interpretacion
            resultado.fecha_resultado = fecha_res_val or fecha_toma_val
            resultado.observaciones = obs_val
        else:
            resultado = Resultado(
                lote_id=lote.id,
                paciente_id=paciente.id,
                prueba_id=prueba.id,
                valor=Decimal(str(valor_num)) if valor_num is not None else None,
                valor_texto=valor_text,
                interpretacion=interpretacion,
                fecha_toma=fecha_toma_val,
                fecha_resultado=fecha_res_val or fecha_toma_val,
                observaciones=obs_val
            )
            db.add(resultado)
        exitosos += 1

    # Actualizar estado del lote
    lote.total_registros = total_filas
    lote.registros_exitosos = exitosos
    lote.registros_error = erroneos

    if erroneos == 0:
        lote.estado = "completado"
    elif exitosos == 0:
        lote.estado = "error"
    else:
        lote.estado = "error_parcial"

    if errors:
        lote.log_errores = json.dumps(errors)

    # Calcular ACR faltantes automáticamente
    await calculate_missing_acr(db, lote.id)

    await db.commit()
    await db.refresh(lote)
    return lote

async def process_horizontal_excel(db: AsyncSession, df: pd.DataFrame, lote: Lote) -> Lote:
    """
    Procesa un archivo Excel en formato horizontal (visitas por fila con columnas de estudios).
    NTS mapea a identificacion (CURP). Número mapea a ID de petición (se guarda en observaciones).
    """
    errors = []
    exitosos = 0
    erroneos = 0
    total_filas = len(df)
    
    # Mapeo de columnas normalizadas
    cols = {normalize_column_name(col): col for col in df.columns}
    
    # Mapeo de metadatos esperados
    metadata_mappings = {
        "fecha": ["fecha"],
        "numero": ["numero", "n_mero", "numero_de_peticion"],
        "nombre": ["nombre_del_paciente", "nombre", "nombre_paciente"],
        "apellidos": ["apellidos", "apellido"],
        "sexo": ["sexo_del_paciente", "sexo", "genero"],
        "fecha_nacimiento": ["fecha_nacimiento", "nacimiento"],
        "nts": ["nts", "curp"]
    }
    
    resolved_meta = {}
    for key, alternatives in metadata_mappings.items():
        found_col = None
        for alt in alternatives:
            norm_alt = normalize_column_name(alt)
            if norm_alt in cols:
                found_col = cols[norm_alt]
                break
        resolved_meta[key] = found_col

    # Identificar columnas que NO son metadatos para tratarlas como estudios
    metadata_columns_in_df = {resolved_meta[k] for k in resolved_meta if resolved_meta[k] is not None}
    
    # Excluir explícitamente otras columnas de metadatos comunes que no son pruebas
    for col in df.columns:
        col_norm = normalize_column_name(col)
        if "edad" in col_norm or "activacion" in col_norm or "adicional" in col_norm or "info" in col_norm:
            metadata_columns_in_df.add(col)
            
    test_columns = [
        col for col in df.columns 
        if col not in metadata_columns_in_df and col.upper() in ["CRTS", "CRE01", "ALBOR", "ACR"]
    ]
    

    # Cargar catálogo de pruebas en caché de memoria para optimizar
    pruebas_result = await db.execute(select(Prueba))
    pruebas_cache = {p.codigo: p for p in pruebas_result.scalars().all()}

    # Procesar cada fila
    for index, row in df.iterrows():
        fila_num = index + 2
        fila_errores = []
        
        # Extraer metadatos
        fecha_raw = row[resolved_meta["fecha"]] if resolved_meta["fecha"] else None
        numero_raw = str(row[resolved_meta["numero"]]).strip() if resolved_meta["numero"] and pd.notna(row[resolved_meta["numero"]]) else ""
        nombre_raw = str(row[resolved_meta["nombre"]]).strip() if resolved_meta["nombre"] and pd.notna(row[resolved_meta["nombre"]]) else ""
        apellidos_raw = str(row[resolved_meta["apellidos"]]).strip() if resolved_meta["apellidos"] and pd.notna(row[resolved_meta["apellidos"]]) else ""
        sexo_raw = str(row[resolved_meta["sexo"]]).strip().upper() if resolved_meta["sexo"] and pd.notna(row[resolved_meta["sexo"]]) else None
        nac_raw = row[resolved_meta["fecha_nacimiento"]] if resolved_meta["fecha_nacimiento"] else None
        nts_raw = str(row[resolved_meta["nts"]]).strip() if resolved_meta["nts"] and pd.notna(row[resolved_meta["nts"]]) else ""

        # Si la fila está completamente vacía (sin metadatos ni identificación), ignorar silenciosamente
        if not nombre_raw and not apellidos_raw and not nts_raw and not numero_raw:
            total_filas -= 1
            continue

        # Identificación del Paciente con lógica de matching
        paciente_id_val = match_patient_identifier(nts_raw, nombre_raw, apellidos_raw, sexo_raw)
        
        if not paciente_id_val:
            if numero_raw:
                paciente_id_val = f"NTS-{numero_raw}"
            else:
                fila_errores.append({"columna": "NTS", "error": "No se pudo identificar al paciente (NTS y Número vacíos)", "valor": ""})

        if not nombre_raw:
            fila_errores.append({"columna": "Nombre_Paciente", "error": "El nombre del paciente es obligatorio", "valor": ""})
        if not apellidos_raw:
            fila_errores.append({"columna": "Apellidos", "error": "Los apellidos del paciente son obligatorios", "valor": ""})

        # Procesar fecha de toma (fecha de la visita)
        fecha_toma_val = parse_date(fecha_raw) if fecha_raw else None
        if not fecha_toma_val:
            fila_errores.append({"columna": "Fecha", "error": "Fecha de toma inválida o vacía", "valor": str(fecha_raw)})

        if fila_errores:
            for err in fila_errores:
                errors.append({"fila": fila_num, **err})
            erroneos += 1
            continue

        # Upsert Paciente
        paciente_res = await db.execute(select(Paciente).where(Paciente.identificacion == paciente_id_val))
        paciente = paciente_res.scalar_one_or_none()
        pac_nac = parse_date(nac_raw) if nac_raw else None
        
        if not paciente:
            paciente = Paciente(
                identificacion=paciente_id_val,
                nombre=nombre_raw,
                apellido=apellidos_raw,
                fecha_nacimiento=pac_nac,
                sexo=sexo_raw
            )
            db.add(paciente)
            await db.flush()
        else:
            if nombre_raw: paciente.nombre = nombre_raw
            if apellidos_raw: paciente.apellido = apellidos_raw
            if pac_nac: paciente.fecha_nacimiento = pac_nac
            if sexo_raw: paciente.sexo = sexo_raw

        # Procesar columnas de pruebas
        fila_exitosos = 0
        for col_name in test_columns:
            valor_raw = str(row[col_name]).strip() if pd.notna(row[col_name]) else ""
            if not valor_raw or valor_raw.lower() in ["nan", "none", "null", ""]:
                continue # Saltar estudios no tomados en esta visita
                
            # Buscar o crear la prueba en el catálogo (auto-creación inteligente)
            prueba_codigo = col_name
            prueba = pruebas_cache.get(prueba_codigo)
            if not prueba:
                # Auto-crear catálogo de prueba
                prueba = Prueba(
                    codigo=prueba_codigo,
                    nombre=f"{prueba_codigo}",
                    categoria="Química Clínica",
                    unidad="",
                    activa=True
                )
                db.add(prueba)
                await db.flush()
                pruebas_cache[prueba_codigo] = prueba

            # Procesar el valor numérico o texto
            valor_num = None
            valor_text = None
            interpretacion = "normal"
            
            try:
                clean_val = valor_raw.replace(",", ".")
                valor_num = float(clean_val)
                interpretacion = calcular_interpretacion(
                    valor_num,
                    prueba.valor_min,
                    prueba.valor_max,
                    prueba.valor_critico_min,
                    prueba.valor_critico_max
                )
            except ValueError:
                valor_text = valor_raw
                interpretacion = "normal"

            # Buscar si ya existe el resultado para esta visita para evitar duplicados
            res_stmt = select(Resultado).where(
                Resultado.paciente_id == paciente.id,
                Resultado.prueba_id == prueba.id,
                Resultado.fecha_toma == fecha_toma_val
            )
            res_query = await db.execute(res_stmt)
            resultado = res_query.scalars().first()

            # Notas adicionales de la petición
            obs_val = f"Petición No. {numero_raw}" if numero_raw else None

            if resultado:
                # Actualizar
                resultado.lote_id = lote.id
                resultado.valor = Decimal(str(valor_num)) if valor_num is not None else None
                resultado.valor_texto = valor_text
                resultado.interpretacion = interpretacion
                resultado.fecha_resultado = fecha_toma_val
                resultado.observaciones = obs_val
            else:
                # Crear nuevo
                resultado = Resultado(
                    lote_id=lote.id,
                    paciente_id=paciente.id,
                    prueba_id=prueba.id,
                    valor=Decimal(str(valor_num)) if valor_num is not None else None,
                    valor_texto=valor_text,
                    interpretacion=interpretacion,
                    fecha_toma=fecha_toma_val,
                    fecha_resultado=fecha_toma_val,
                    observaciones=obs_val
                )
                db.add(resultado)
            fila_exitosos += 1

        if fila_exitosos > 0:
            exitosos += 1
        else:
            # Si una fila tiene metadatos válidos pero no tiene estudios cargados,
            # se salta silenciosamente sin registrar error para el usuario.
            total_filas -= 1

    # Actualizar estado del lote
    lote.total_registros = total_filas
    lote.registros_exitosos = exitosos
    lote.registros_error = erroneos

    if erroneos == 0:
        lote.estado = "completado"
    elif exitosos == 0:
        lote.estado = "error"
    else:
        lote.estado = "error_parcial"

    if errors:
        lote.log_errores = json.dumps(errors)

    # Calcular ACR faltantes automáticamente
    await calculate_missing_acr(db, lote.id)

    await db.commit()
    await db.refresh(lote)
    return lote

async def calculate_missing_acr(db: AsyncSession, lote_id: int):
    """
    Busca visitas en el lote que tengan ALBOR y CRE01 pero les falte ACR,
    y calcula/crea el resultado de ACR de forma automática.
    """
    stmt = select(Resultado).where(Resultado.lote_id == lote_id)
    res = await db.execute(stmt)
    resultados = res.scalars().all()
    
    # Agrupar por visita
    visitas = {}
    for r in resultados:
        # Cargar la relación prueba para acceder a su código
        prueba_res = await db.execute(select(Prueba).where(Prueba.id == r.prueba_id))
        prueba = prueba_res.scalar_one()
        key = (r.paciente_id, r.fecha_toma)
        if key not in visitas:
            visitas[key] = {}
        visitas[key][prueba.codigo.upper()] = r
        
    acr_prueba_res = await db.execute(select(Prueba).where(Prueba.codigo == "ACR"))
    acr_prueba = acr_prueba_res.scalar_one_or_none()
    if not acr_prueba:
        acr_prueba = Prueba(
            codigo="ACR",
            nombre="Relación Albúmina/Creatinina",
            categoria="Química Clínica",
            unidad="mg/g",
            activa=True
        )
        db.add(acr_prueba)
        await db.flush()
        
    for (paciente_id, fecha_toma), pruebas_map in visitas.items():
        if "ALBOR" in pruebas_map and "CRE01" in pruebas_map and "ACR" not in pruebas_map:
            albor_val = float(pruebas_map["ALBOR"].valor) if pruebas_map["ALBOR"].valor is not None else None
            cre01_val = float(pruebas_map["CRE01"].valor) if pruebas_map["CRE01"].valor is not None else None
            
            if albor_val is not None and cre01_val is not None and cre01_val > 0:
                acr_val = (albor_val / cre01_val) * 100
                ref_res = pruebas_map["ALBOR"]
                
                existing_stmt = select(Resultado).where(
                    Resultado.paciente_id == paciente_id,
                    Resultado.prueba_id == acr_prueba.id,
                    Resultado.fecha_toma == fecha_toma
                )
                existing_res = await db.execute(existing_stmt)
                existing = existing_res.scalars().first()
                
                if existing:
                    existing.valor = Decimal(str(round(acr_val, 2)))
                    existing.lote_id = lote_id
                else:
                    new_acr = Resultado(
                        lote_id=lote_id,
                        paciente_id=paciente_id,
                        prueba_id=acr_prueba.id,
                        valor=Decimal(str(round(acr_val, 2))),
                        interpretacion="normal",
                        fecha_toma=fecha_toma,
                        fecha_resultado=fecha_toma,
                        observaciones="Calculado automáticamente (ALBOR/CRE01)"
                    )
                    db.add(new_acr)
    await db.flush()

async def process_tamizaje_excel(db: AsyncSession, file_content: bytes, filename: str, usuario_id: int) -> dict:
    """
    Lee y valida un archivo Excel de tamizaje de pacientes (Google Forms), creando o actualizando los perfiles.
    """
    lote = Lote(
        nombre=filename,
        descripcion=f"Carga de Tamizaje {filename}",
        usuario_id=usuario_id,
        estado="procesando",
        total_registros=0,
        registros_exitosos=0,
        registros_error=0,
        log_errores=None
    )
    db.add(lote)
    await db.commit()
    await db.refresh(lote)

    errors = []
    exitosos = 0
    erroneos = 0

    try:
        df = pd.read_excel(io.BytesIO(file_content), keep_default_na=False)
        df = df.replace("", None)
    except Exception as e:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "columna": "archivo", "error": f"No se pudo leer el archivo: {str(e)}", "valor": ""}])
        await db.commit()
        return {"lote": lote, "resumen": {"exitosos": 0, "erroneos": 0}}

    total_filas = len(df)
    if total_filas == 0:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "columna": "archivo", "error": "El archivo Excel está vacío", "valor": ""}])
        await db.commit()
        return {"lote": lote, "resumen": {"exitosos": 0, "erroneos": 0}}

    cols = {normalize_column_name(col): col for col in df.columns}
    
    mappings = {
        "fecha": ["fecha"],
        "nombre": ["nombre"],
        "apellido_paterno": ["apellido_paterno"],
        "apellido_materno": ["apellido_materno"],
        "sexo": ["sexo"],
        "telefono": ["telefono_de_contacto"],
        "email": ["correo_electronico"],
        "fecha_nacimiento": ["fecha_de_nacimiento"],
        "edad": ["edad"],
        "estado_origen": ["estado_de_origen"],
        "curp": ["curp"],
        "domicilio": ["domicilio_calle_numero_colonia"],
        "codigo_postal": ["codigo_postal"],
        "estado_residencia": ["estado_de_residencia"],
        "municipio": ["muncipio_de_residencia", "municipio_de_residencia"],
        "peso": ["peso"],
        "estatura": ["estatura"],
        "derechohabiencia": ["derechohabiencia"],
        "suplemento": ["toma_alg_n_suplemento", "suplemento", "toma_algun_suplemento", "toma_alg"],
        "tipo_agua": ["_que_tipo_de_agua_toma", "tipo_agua", "que_tipo_de_agua_toma", "que_tipo"],
        "cocina_agua": ["_cocina_con_agua_de_la_llave", "cocina_agua", "cocina_con_agua_de_la_llave", "cocina_con_agua"],
        "padecimientos": ["padecimientos_seleccionar_1_o_varios", "padecimientos"]
    }
    
    resolved_meta = {}
    for key, alternatives in mappings.items():
        found_col = None
        for alt in alternatives:
            for c_norm in cols:
                if alt in c_norm:
                    found_col = cols[c_norm]
                    break
            if found_col:
                break
        resolved_meta[key] = found_col

    for index, row in df.iterrows():
        fila_num = index + 2
        
        curp = str(row[resolved_meta["curp"]]).strip().upper() if resolved_meta.get("curp") and pd.notna(row[resolved_meta["curp"]]) else ""
        nombre = str(row[resolved_meta["nombre"]]).strip() if resolved_meta.get("nombre") and pd.notna(row[resolved_meta["nombre"]]) else ""
        ap_pat = str(row[resolved_meta["apellido_paterno"]]).strip() if resolved_meta.get("apellido_paterno") and pd.notna(row[resolved_meta["apellido_paterno"]]) else ""
        ap_mat = str(row[resolved_meta["apellido_materno"]]).strip() if resolved_meta.get("apellido_materno") and pd.notna(row[resolved_meta["apellido_materno"]]) else ""
        
        sexo_raw = str(row[resolved_meta["sexo"]]).strip().lower() if resolved_meta.get("sexo") and pd.notna(row[resolved_meta["sexo"]]) else ""
        sexo = "M" if "masculino" in sexo_raw else ("F" if "femenino" in sexo_raw else None)
        
        if not curp and not nombre:
            erroneos += 1
            errors.append({"fila": fila_num, "columna": "identidad", "error": "Falta CURP y Nombre", "valor": ""})
            continue

        paciente_id_val = match_patient_identifier(curp, nombre, ap_pat, sexo)
        if not paciente_id_val:
            paciente_id_val = curp if curp else f"{nombre.split()[0].upper()[:4]}{ap_pat.upper()[:2]}XXXXXX"

        paciente_res = await db.execute(select(Paciente).where(Paciente.identificacion == paciente_id_val))
        paciente = paciente_res.scalar_one_or_none()

        fn_raw = row[resolved_meta["fecha_nacimiento"]] if resolved_meta.get("fecha_nacimiento") else None
        fn = parse_date(fn_raw) if fn_raw else None

        tel = str(row[resolved_meta["telefono"]]).strip() if resolved_meta.get("telefono") and pd.notna(row[resolved_meta["telefono"]]) else None
        email = str(row[resolved_meta["email"]]).strip() if resolved_meta.get("email") and pd.notna(row[resolved_meta["email"]]) else None
        domicilio = str(row[resolved_meta["domicilio"]]).strip() if resolved_meta.get("domicilio") and pd.notna(row[resolved_meta["domicilio"]]) else None
        cp = str(row[resolved_meta["codigo_postal"]]).strip() if resolved_meta.get("codigo_postal") and pd.notna(row[resolved_meta["codigo_postal"]]) else None
        edo_res = str(row[resolved_meta["estado_residencia"]]).strip() if resolved_meta.get("estado_residencia") and pd.notna(row[resolved_meta["estado_residencia"]]) else None
        mun_res = str(row[resolved_meta["municipio"]]).strip() if resolved_meta.get("municipio") and pd.notna(row[resolved_meta["municipio"]]) else None
        derecho = str(row[resolved_meta["derechohabiencia"]]).strip() if resolved_meta.get("derechohabiencia") and pd.notna(row[resolved_meta["derechohabiencia"]]) else None
        sup = str(row[resolved_meta["suplemento"]]).strip() if resolved_meta.get("suplemento") and pd.notna(row[resolved_meta["suplemento"]]) else None
        t_agua = str(row[resolved_meta["tipo_agua"]]).strip() if resolved_meta.get("tipo_agua") and pd.notna(row[resolved_meta["tipo_agua"]]) else None
        c_agua = str(row[resolved_meta["cocina_agua"]]).strip() if resolved_meta.get("cocina_agua") and pd.notna(row[resolved_meta["cocina_agua"]]) else None
        pad = str(row[resolved_meta["padecimientos"]]).strip() if resolved_meta.get("padecimientos") and pd.notna(row[resolved_meta["padecimientos"]]) else None
        
        peso_raw = row[resolved_meta["peso"]] if resolved_meta.get("peso") else None
        peso = None
        if peso_raw:
            try:
                peso = Decimal(str(peso_raw))
            except: pass
            
        est_raw = row[resolved_meta["estatura"]] if resolved_meta.get("estatura") else None
        estatura = None
        if est_raw:
            try:
                estatura = Decimal(str(est_raw))
            except: pass

        if not paciente:
            paciente = Paciente(
                identificacion=paciente_id_val,
                nombre=nombre,
                apellido=ap_pat,
                apellido_materno=ap_mat,
                fecha_nacimiento=fn,
                sexo=sexo,
                telefono=tel,
                email=email,
                domicilio=domicilio,
                codigo_postal=cp,
                estado_residencia=edo_res,
                municipio_residencia=mun_res,
                peso=peso,
                estatura=estatura,
                derechohabiencia=derecho,
                suplemento_detalle=sup,
                tipo_agua=t_agua,
                cocina_agua_llave=c_agua,
                padecimientos=pad
            )
            db.add(paciente)
        else:
            if nombre: paciente.nombre = nombre
            if ap_pat: paciente.apellido = ap_pat
            if ap_mat: paciente.apellido_materno = ap_mat
            if fn: paciente.fecha_nacimiento = fn
            if sexo: paciente.sexo = sexo
            if tel: paciente.telefono = tel
            if email: paciente.email = email
            if domicilio: paciente.domicilio = domicilio
            if cp: paciente.codigo_postal = cp
            if edo_res: paciente.estado_residencia = edo_res
            if mun_res: paciente.municipio_residencia = mun_res
            if peso is not None: paciente.peso = peso
            if estatura is not None: paciente.estatura = estatura
            if derecho: paciente.derechohabiencia = derecho
            if sup: paciente.suplemento_detalle = sup
            if t_agua: paciente.tipo_agua = t_agua
            if c_agua: paciente.cocina_agua_llave = c_agua
            if pad: paciente.padecimientos = pad

        exitosos += 1

    lote.total_registros = total_filas
    lote.registros_exitosos = exitosos
    lote.registros_error = erroneos

    if erroneos == 0:
        lote.estado = "completado"
    elif exitosos == 0:
        lote.estado = "error"
    else:
        lote.estado = "error_parcial"

    if errors:
        lote.log_errores = json.dumps(errors)

    await db.commit()
    await db.refresh(lote)
    return {"lote": lote, "resumen": {"exitosos": exitosos, "erroneos": erroneos}}

