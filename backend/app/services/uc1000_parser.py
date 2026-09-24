"""
Parser para el archivo CSV del UC-1000 (analizador de tiras reactivas).

Estructura del CSV:
  - Fila 0: Cabecera de grupo (UC-1000, URO, BLD, CRE, ALB …)
  - Fila 1: Cabecera de sub-columna (Version, Id, RackNo, … Conc …)
  - Filas 2+: Datos

Columnas relevantes (índice 0-based):
  Col2  (idx 1)  → ID del paciente (CURP)
  Col9  (idx 8)  → Fecha de toma  (DD/MM/YYYY)
  Col75 (idx 74) → Creatinina urinaria (CRE, mg/dL)
  Col81 (idx 80) → Albúmina (ALB, mg/L)

Jerarquía de fuentes:
  Vitros > Tira UC-1000

  Un valor con fuente="vitros" NUNCA es sobreescrito por la tira.
  Un valor con fuente="tira_uc1000" SÍ puede ser sobreescrito por Vitros (en el
  parser de Excel) o actualizado por una nueva carga de tira.

Fórmula ACR:
  ACR (mg/g) = (Albúmina mg/L ÷ Creatinina mg/dL) × 100
"""

import io
import json
import csv
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Lote, Paciente, Prueba, Resultado
from app.utils.validators import calcular_interpretacion, interpretar_valor_texto

# ---------------------------------------------------------------------------
# Constantes de mapeo por ÍNDICE de columna (0-based)
# ---------------------------------------------------------------------------
IDX_CURP   = 1   # Col2
IDX_FECHA  = 8   # Col9
IDX_CRE    = 74  # Col75
IDX_ALB    = 80  # Col81

CODIGO_ALB  = "ALBOR"
CODIGO_CRE  = "CRE01"
CODIGO_ACR  = "ACR"

FUENTE_TIRA   = "tira_uc1000"
FUENTE_VITROS = "vitros"

# ---------------------------------------------------------------------------
# Constantes para detección de ID de petición del hospital
# ---------------------------------------------------------------------------
# Cuando el UC-1000 recibe muestra de orina, el campo ID tiene la forma:
#   <modificador 2 dígitos><id_peticion 8 dígitos>  →  total 10 dígitos
# Ejemplo: 1799921184  →  17 (orina) + 99921184 (ID del hospital)
MODIFICADOR_LEN  = 2   # Longitud del prefijo de tipo de muestra
ID_PETICION_LEN  = 8   # Longitud del ID de petición del hospital
ID_CON_MOD_LEN   = MODIFICADOR_LEN + ID_PETICION_LEN  # 10 dígitos en total
CURP_LEN         = 18  # Longitud esperada de una CURP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_value(raw: str) -> str:
    """Elimina espacios, asteriscos y caracteres de padding del UC-1000."""
    return raw.strip().lstrip("*").strip()


def _parse_numeric(raw: str) -> Optional[float]:
    """
    Intenta convertir la cadena a float.
    Retorna None si el valor es vacío, 'over', '-', etc.
    """
    val = _clean_value(raw)
    if not val or val.lower() in ("-", "over", ">=", "<=", ""):
        return None
    # El UC-1000 a veces incluye ">=" o "<=" antes del número
    for prefix in (">=", "<=", ">", "<"):
        if val.startswith(prefix):
            val = val[len(prefix):]
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return None


def _parse_over(raw: str) -> bool:
    """Devuelve True si el valor está fuera del rango medible ("over")."""
    val = _clean_value(raw).lower()
    return "over" in val


def _parse_fecha(raw: str) -> Optional[date]:
    """Parsea la fecha DD/MM/YYYY del UC-1000."""
    val = _clean_value(raw)
    if not val:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Función de upsert con jerarquía de fuentes
# ---------------------------------------------------------------------------

async def _upsert_resultado_jerarquico(
    db: AsyncSession,
    paciente_id: int,
    prueba: Prueba,
    lote_id: int,
    fecha_toma: date,
    valor_num: Optional[float],
    valor_texto: Optional[str],
    fuente_nueva: str,
    observaciones: Optional[str] = None,
) -> bool:
    """
    Crea o actualiza un Resultado respetando la jerarquía de fuentes.

    Reglas:
      - Si NO existe → crea con la fuente dada.
      - Si existe con fuente=vitros y fuente_nueva=tira → NO sobreescribe (protección).
      - En cualquier otro caso → actualiza.

    Retorna True si se creó/actualizó, False si fue bloqueado.
    """
    stmt = select(Resultado).where(
        Resultado.paciente_id == paciente_id,
        Resultado.prueba_id   == prueba.id,
        Resultado.fecha_toma  == fecha_toma,
    )
    res_q = await db.execute(stmt)
    existing = res_q.scalars().first()

    if existing:
        # Protección: Vitros > Tira
        if existing.fuente == FUENTE_VITROS and fuente_nueva == FUENTE_TIRA:
            return False  # Valor Vitros protegido

        existing.lote_id      = lote_id
        existing.valor        = Decimal(str(round(valor_num, 4))) if valor_num is not None else None
        existing.valor_texto  = valor_texto
        existing.fuente       = fuente_nueva
        existing.observaciones = observaciones
        if valor_num is not None:
            existing.interpretacion = calcular_interpretacion(
                valor_num, prueba.valor_min, prueba.valor_max,
                prueba.valor_critico_min, prueba.valor_critico_max
            )
        else:
            existing.interpretacion = interpretar_valor_texto(valor_texto)
    else:
        interpretacion = "normal"
        if valor_num is not None:
            interpretacion = calcular_interpretacion(
                valor_num, prueba.valor_min, prueba.valor_max,
                prueba.valor_critico_min, prueba.valor_critico_max
            )
        else:
            interpretacion = interpretar_valor_texto(valor_texto)
        new_r = Resultado(
            lote_id      = lote_id,
            paciente_id  = paciente_id,
            prueba_id    = prueba.id,
            valor        = Decimal(str(round(valor_num, 4))) if valor_num is not None else None,
            valor_texto  = valor_texto,
            interpretacion = interpretacion,
            fecha_toma   = fecha_toma,
            fecha_resultado = fecha_toma,
            fuente       = fuente_nueva,
            observaciones = observaciones,
        )
        db.add(new_r)

    return True


# ---------------------------------------------------------------------------
# Cálculo de ACR con jerarquía de fuentes
# ---------------------------------------------------------------------------

async def calculate_acr_for_patient(
    db: AsyncSession,
    paciente_id: int,
    fecha_toma: date,
    lote_id: int,
    prueba_alb: Prueba,
    prueba_cre: Prueba,
    prueba_acr: Prueba,
) -> Optional[float]:
    """
    Calcula el ACR usando los mejores valores disponibles (Vitros > Tira).
    Actualiza/crea el resultado ACR en la BD.
    Retorna el ACR calculado o None si faltan datos.
    """
    # Recuperar mejor albúmina (preferir Vitros)
    alb_stmt = select(Resultado).where(
        Resultado.paciente_id == paciente_id,
        Resultado.prueba_id   == prueba_alb.id,
        Resultado.fecha_toma  == fecha_toma,
    )
    alb_q   = await db.execute(alb_stmt)
    alb_res = alb_q.scalars().first()

    # Recuperar mejor creatinina (preferir Vitros)
    cre_stmt = select(Resultado).where(
        Resultado.paciente_id == paciente_id,
        Resultado.prueba_id   == prueba_cre.id,
        Resultado.fecha_toma  == fecha_toma,
    )
    cre_q   = await db.execute(cre_stmt)
    cre_res = cre_q.scalars().first()

    if not alb_res or not cre_res:
        return None
    if alb_res.valor is None or cre_res.valor is None:
        return None

    alb_val = float(alb_res.valor)  # mg/L
    cre_val = float(cre_res.valor)  # mg/dL

    if cre_val <= 0:
        return None

    # ACR = (Alb mg/L ÷ (Creat mg/dL * 10 mg/L)) * 1000 mg/g = (Alb ÷ Creat) * 100
    acr_val = (alb_val / cre_val) * 100

    # La fuente del ACR refleja la fuente menos confiable de los dos valores
    if alb_res.fuente == FUENTE_VITROS and cre_res.fuente == FUENTE_VITROS:
        fuente_acr = FUENTE_VITROS
    else:
        fuente_acr = FUENTE_TIRA

    obs = f"Calculado: ALB({alb_res.fuente}) / CRE({cre_res.fuente})"

    acr_stmt = select(Resultado).where(
        Resultado.paciente_id == paciente_id,
        Resultado.prueba_id   == prueba_acr.id,
        Resultado.fecha_toma  == fecha_toma,
    )
    acr_q   = await db.execute(acr_stmt)
    existing_acr = acr_q.scalars().first()

    acr_decimal = Decimal(str(round(acr_val, 2)))
    interpretacion = calcular_interpretacion(
        acr_val, prueba_acr.valor_min, prueba_acr.valor_max,
        prueba_acr.valor_critico_min, prueba_acr.valor_critico_max
    )

    if existing_acr:
        existing_acr.valor        = acr_decimal
        existing_acr.lote_id      = lote_id
        existing_acr.fuente       = fuente_acr
        existing_acr.interpretacion = interpretacion
        existing_acr.observaciones  = obs
    else:
        db.add(Resultado(
            lote_id       = lote_id,
            paciente_id   = paciente_id,
            prueba_id     = prueba_acr.id,
            valor         = acr_decimal,
            interpretacion = interpretacion,
            fecha_toma    = fecha_toma,
            fecha_resultado = fecha_toma,
            fuente        = fuente_acr,
            observaciones = obs,
        ))

    await db.flush()
    return acr_val


# ---------------------------------------------------------------------------
# Resolución de paciente: CURP o ID de petición del hospital
# ---------------------------------------------------------------------------

async def _resolve_paciente(
    db: AsyncSession,
    raw_id: str,
) -> tuple:
    """
    Resuelve el paciente a partir del valor de la columna ID del UC-1000.

    Reglas de detección:
      - 18 caracteres alfanuméricos → CURP. Busca por Paciente.identificacion.
      - 10 dígitos numéricos        → Modificador (2) + ID de petición (8).
                                      Quita el prefijo, busca un Resultado cuyas
                                      observaciones contengan "Petición No. <id>".
      - Cualquier otro caso          → formato no reconocido, error.

    Retorna: (paciente_or_None, error_str_or_None)
      - (Paciente, None)  → paciente encontrado.
      - (None, str)       → no encontrado; str contiene el mensaje de error.
    """
    if not raw_id:
        return None, "ID de paciente vacío"

    # ── Caso 1: CURP (18 caracteres) ──────────────────────────────────────
    if len(raw_id) == CURP_LEN:
        pac_res = await db.execute(
            select(Paciente).where(Paciente.identificacion == raw_id)
        )
        paciente = pac_res.scalar_one_or_none()
        if not paciente:
            return None, (
                f"No se encontró un paciente registrado con CURP '{raw_id}'. "
                "El paciente debe existir antes de cargar resultados de tira."
            )
        return paciente, None

    # ── Caso 2: ID de petición con modificador (10 dígitos numéricos) ─────
    if len(raw_id) == ID_CON_MOD_LEN and raw_id.isdigit():
        id_peticion = raw_id[MODIFICADOR_LEN:]  # quitar los 2 dígitos del modificador
        patron = f"Petición No. {id_peticion}"

        # Buscar cualquier Resultado cuyas observaciones contengan ese número
        res_stmt = select(Resultado).where(
            Resultado.observaciones.ilike(f"%{patron}%")
        ).limit(1)
        res_q = await db.execute(res_stmt)
        resultado_ref = res_q.scalar_one_or_none()

        if not resultado_ref:
            return None, (
                f"No existe ningún registro con Petición No. {id_peticion} "
                "(ID de UC-1000: '{raw_id}'). "
                "Sube primero el Excel del Vitros para registrar al paciente."
            )

        # Recuperar el paciente a través del resultado encontrado
        pac_res = await db.execute(
            select(Paciente).where(Paciente.id == resultado_ref.paciente_id)
        )
        paciente = pac_res.scalar_one_or_none()
        if not paciente:
            return None, (
                f"Se encontró la Petición No. {id_peticion} pero el paciente "
                "asociado no existe en la base de datos."
            )
        return paciente, None

    # ── Caso 3: Formato no reconocido ─────────────────────────────────────
    return None, (
        f"El ID '{raw_id}' no es una CURP válida (18 caracteres) "
        f"ni un ID de petición con modificador ({ID_CON_MOD_LEN} dígitos numéricos)."
    )


# ---------------------------------------------------------------------------
# Obtener o crear prueba del catálogo
# ---------------------------------------------------------------------------

async def _get_or_create_prueba(
    db: AsyncSession,
    cache: dict,
    codigo: str,
    nombre: str,
    unidad: str,
    valor_max: Optional[float] = None,
) -> Prueba:
    if codigo in cache:
        return cache[codigo]

    res = await db.execute(select(Prueba).where(Prueba.codigo == codigo))
    prueba = res.scalar_one_or_none()

    if not prueba:
        prueba = Prueba(
            codigo   = codigo,
            nombre   = nombre,
            categoria = "Química Clínica",
            unidad   = unidad,
            valor_max = Decimal(str(valor_max)) if valor_max is not None else None,
            activa   = True,
        )
        db.add(prueba)
        await db.flush()

    cache[codigo] = prueba
    return prueba


# ---------------------------------------------------------------------------
# Parser principal del UC-1000
# ---------------------------------------------------------------------------

async def process_uc1000_csv(
    db: AsyncSession,
    file_content: bytes,
    filename: str,
    usuario_id: int,
) -> Lote:
    """
    Lee el CSV del UC-1000 y carga los resultados de albúmina y creatinina
    de tira reactiva. Respeta la jerarquía Vitros > Tira para no sobreescribir
    valores de mayor calidad. Calcula el ACR automáticamente.
    """
    # 1. Crear lote
    lote = Lote(
        nombre       = filename,
        descripcion  = f"Carga UC-1000 tira reactiva — {filename}",
        usuario_id   = usuario_id,
        estado       = "procesando",
        total_registros      = 0,
        registros_exitosos   = 0,
        registros_error      = 0,
        log_errores  = None,
    )
    db.add(lote)
    await db.commit()
    await db.refresh(lote)

    errors   = []
    exitosos = 0
    erroneos = 0

    # 2. Decodificar el CSV
    try:
        text = file_content.decode("utf-8", errors="replace")
    except Exception as e:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "error": f"No se pudo decodificar el archivo: {e}"}])
        await db.commit()
        return lote

    reader = list(csv.reader(io.StringIO(text)))

    # Validar que es un archivo UC-1000
    if not reader or "UC-1000" not in reader[0][0]:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "error": "El archivo no es un CSV del UC-1000 válido"}])
        await db.commit()
        return lote

    # Filas de datos empiezan en el índice 2 (después de las 2 cabeceras)
    data_rows = reader[2:]
    total_filas = len([r for r in data_rows if any(c.strip() for c in r)])

    if total_filas == 0:
        lote.estado = "error"
        lote.log_errores = json.dumps([{"fila": 0, "error": "El archivo no contiene registros de datos"}])
        await db.commit()
        return lote

    # 3. Caché de pruebas
    prueba_cache: dict = {}
    prueba_alb = await _get_or_create_prueba(db, prueba_cache, CODIGO_ALB,
                                              "Albúmina Urinaria", "mg/L")
    prueba_cre = await _get_or_create_prueba(db, prueba_cache, CODIGO_CRE,
                                              "Creatinina Urinaria", "mg/dL")
    prueba_acr = await _get_or_create_prueba(db, prueba_cache, CODIGO_ACR,
                                              "Relación Albúmina/Creatinina", "mg/g",
                                              valor_max=30.0)

    # 4. Procesar cada fila
    filas_contadas = 0
    for row_idx, row in enumerate(data_rows):
        fila_num = row_idx + 3  # 1-indexed, offset de 2 cabeceras

        # Saltar filas vacías
        if not any(c.strip() for c in row):
            continue
        filas_contadas += 1

        # Extraer columnas por índice
        id_raw    = row[IDX_CURP].strip()  if len(row) > IDX_CURP  else ""
        fecha_raw = row[IDX_FECHA].strip() if len(row) > IDX_FECHA else ""
        cre_raw   = row[IDX_CRE].strip()   if len(row) > IDX_CRE   else ""
        alb_raw   = row[IDX_ALB].strip()   if len(row) > IDX_ALB   else ""

        # ID del paciente (CURP o ID de petición del hospital con modificador)
        id_valor = id_raw.upper()
        if not id_valor:
            # Fila sin ID: es una muestra de control/calibración del equipo.
            # Se ignora silenciosamente (no cuenta como error ni como éxito).
            filas_contadas -= 1
            continue

        # Fecha de toma (usamos la del CSV, Col9)
        fecha_toma = _parse_fecha(fecha_raw)
        if not fecha_toma:
            # Si no hay fecha, usamos hoy como fallback y anotamos en observaciones
            from datetime import date as date_today
            fecha_toma = date_today.today()

        # Resolver paciente: CURP directa o ID de petición con modificador
        paciente, resolve_error = await _resolve_paciente(db, id_valor)

        if resolve_error:
            errors.append({
                "fila": fila_num,
                "columna": "ID (Col2)",
                "error": resolve_error,
                "valor": id_raw,
            })
            erroneos += 1
            continue

        # Parsear valores numéricos
        alb_num   = _parse_numeric(alb_raw)
        alb_over  = _parse_over(alb_raw)
        cre_num   = _parse_numeric(cre_raw)
        cre_over  = _parse_over(cre_raw)

        alb_texto = "over" if alb_over and alb_num is None else None
        cre_texto = "over" if cre_over and cre_num is None else None

        fila_ok = True

        # Cargar Albúmina (ALBOR)
        actualizado_alb = await _upsert_resultado_jerarquico(
            db           = db,
            paciente_id  = paciente.id,
            prueba       = prueba_alb,
            lote_id      = lote.id,
            fecha_toma   = fecha_toma,
            valor_num    = alb_num,
            valor_texto  = alb_texto,
            fuente_nueva = FUENTE_TIRA,
            observaciones = f"Tira UC-1000 — {filename}",
        )
        if not actualizado_alb:
            errors.append({
                "fila": fila_num,
                "columna": "ALB (Col81)",
                "error": "El valor de Albúmina no se cargó porque ya existe un valor de Vitros (mayor jerarquía).",
                "valor": alb_raw,
            })
            # No cuenta como error crítico, el paciente sí se procesó
            fila_ok = False

        # Cargar Creatinina (CRE01)
        actualizado_cre = await _upsert_resultado_jerarquico(
            db           = db,
            paciente_id  = paciente.id,
            prueba       = prueba_cre,
            lote_id      = lote.id,
            fecha_toma   = fecha_toma,
            valor_num    = cre_num,
            valor_texto  = cre_texto,
            fuente_nueva = FUENTE_TIRA,
            observaciones = f"Tira UC-1000 — {filename}",
        )
        if not actualizado_cre:
            errors.append({
                "fila": fila_num,
                "columna": "CRE (Col75)",
                "error": "El valor de Creatinina no se cargó porque ya existe un valor de Vitros (mayor jerarquía).",
                "valor": cre_raw,
            })
            fila_ok = False

        # Calcular ACR solo si hay datos suficientes
        if alb_num is not None and cre_num is not None:
            await calculate_acr_for_patient(
                db          = db,
                paciente_id = paciente.id,
                fecha_toma  = fecha_toma,
                lote_id     = lote.id,
                prueba_alb  = prueba_alb,
                prueba_cre  = prueba_cre,
                prueba_acr  = prueba_acr,
            )

        exitosos += 1

    # 5. Actualizar estado del lote
    lote.total_registros    = filas_contadas
    lote.registros_exitosos = exitosos
    lote.registros_error    = erroneos

    if erroneos == 0:
        lote.estado = "completado"
    elif exitosos == 0:
        lote.estado = "error"
    else:
        lote.estado = "error_parcial"

    if errors:
        lote.log_errores = json.dumps(errors, ensure_ascii=False)

    await db.commit()
    await db.refresh(lote)
    return lote
