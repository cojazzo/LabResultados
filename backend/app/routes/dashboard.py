from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, cast, Date
from app.database import get_db
from app.models import Resultado, Paciente, ReporteGenerado, Envio, Prueba, User
from app.core.security import get_current_user
from app.config import get_settings
from app.services.riesgo_renal import clasificar_pacientes, clasificar_persona, armar_matriz, CODIGOS_RENALES
from app.utils.validators import nombre_completo_paciente
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta

router = APIRouter(prefix="/dashboard", tags=["Dashboard Estadísticas"])


# ── Esquemas ──────────────────────────────────────────────────────────────────
#
# Criterio de conteo: el dashboard cuenta PERSONAS, no determinaciones. Una persona
# que se hace ACR, creatinina urinaria, creatinina sérica y albúmina cuenta como 1.

class ResumenResponse(BaseModel):
    total_personas: int                 # personas con al menos un resultado en el periodo
    total_determinaciones: int          # resultados individuales (informativo)
    personas_con_alteraciones: int      # personas con al menos un resultado fuera de lo normal
    personas_clasificadas: int          # personas con TFG y/o ACR para clasificar riesgo KDIGO
    personas_riesgo_renal: int          # clasificadas con riesgo moderado o mayor
    total_reportes: int
    total_envios_exitosos: int
    total_envios_fallidos: int
    dias_promedio_entrega: Optional[float] = None   # toma -> resultado; None si no hay datos
    # Compatibilidad con consumidores anteriores (verify_e2e, API pública)
    total_pruebas: int
    total_pacientes: int
    porcentaje_fuera_rango: float

class TendenciaItem(BaseModel):
    periodo: str
    cantidad: int    # personas distintas atendidas en ese periodo

class AnormalesDistribucion(BaseModel):
    interpretacion: str
    cantidad: int

class TopPrueba(BaseModel):
    codigo: str
    nombre: str
    cantidad: int    # personas distintas con esa prueba

class KdigoCelda(BaseModel):
    g: str
    a: str
    cantidad: int
    color: str       # green | yellow | orange | red | gray

class KdigoPorRiesgo(BaseModel):
    bajo: int
    moderado: int
    alto: int
    muy_alto: int

class RiesgoKdigoResponse(BaseModel):
    filas: List[str]
    columnas: List[str]
    celdas: List[KdigoCelda]
    total_personas: int
    sin_clasificar: int
    completas: int
    por_riesgo: KdigoPorRiesgo


# ── Utilidades ────────────────────────────────────────────────────────────────

def _validar_rango(desde: Optional[date], hasta: Optional[date]) -> None:
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=400, detail="'desde' no puede ser posterior a 'hasta'.")

def _filtro_fecha_toma(desde: Optional[date], hasta: Optional[date]) -> list:
    condiciones = []
    if desde:
        condiciones.append(Resultado.fecha_toma >= desde)
    if hasta:
        condiciones.append(Resultado.fecha_toma <= hasta)
    return condiciones

def _filtro_fecha_dt(columna, desde: Optional[date], hasta: Optional[date]) -> list:
    """Filtro por día sobre una columna datetime (reportes, envíos)."""
    condiciones = []
    if desde:
        condiciones.append(cast(columna, Date) >= desde)
    if hasta:
        condiciones.append(cast(columna, Date) <= hasta)
    return condiciones


async def build_resumen(
    db: AsyncSession, desde: Optional[date] = None, hasta: Optional[date] = None
) -> ResumenResponse:
    filtro = _filtro_fecha_toma(desde, hasta)

    # 1. Personas y determinaciones del periodo
    total_personas = (await db.execute(
        select(func.count(func.distinct(Resultado.paciente_id))).where(*filtro)
    )).scalar() or 0
    total_determinaciones = (await db.execute(
        select(func.count(Resultado.id)).where(*filtro)
    )).scalar() or 0

    # 2. Personas con algún resultado fuera de lo normal
    personas_alteradas = (await db.execute(
        select(func.count(func.distinct(Resultado.paciente_id))).where(
            *filtro, Resultado.interpretacion.isnot(None), Resultado.interpretacion != "normal"
        )
    )).scalar() or 0
    porcentaje = round(personas_alteradas / total_personas * 100, 1) if total_personas else 0.0

    # 3. Riesgo renal KDIGO por persona (misma clasificación que el reporte PDF)
    clasificaciones = await clasificar_pacientes(db, desde, hasta)
    clasificadas = [c for c in clasificaciones if c["color"] != "gray"]
    en_riesgo = [c for c in clasificadas if c["color"] in ("yellow", "orange", "red")]

    # 4. Reportes y envíos del periodo
    total_reportes = (await db.execute(
        select(func.count(ReporteGenerado.id)).where(
            *_filtro_fecha_dt(ReporteGenerado.fecha_generacion, desde, hasta)
        )
    )).scalar() or 0

    filtro_envio = _filtro_fecha_dt(Envio.created_at, desde, hasta)
    envios_ok = (await db.execute(
        select(func.count(Envio.id)).where(Envio.estado == "enviado", *filtro_envio)
    )).scalar() or 0
    envios_fallidos = (await db.execute(
        select(func.count(Envio.id)).where(Envio.estado == "fallido", *filtro_envio)
    )).scalar() or 0

    # 5. Tiempo real de entrega: días entre la toma y la fecha del resultado
    fechas = (await db.execute(
        select(Resultado.fecha_toma, Resultado.fecha_resultado).where(
            *filtro, Resultado.fecha_resultado.isnot(None)
        )
    )).all()
    dias = [(fr - ft).days for ft, fr in fechas if fr >= ft]
    dias_promedio = round(sum(dias) / len(dias), 1) if dias else None

    return ResumenResponse(
        total_personas=total_personas,
        total_determinaciones=total_determinaciones,
        personas_con_alteraciones=personas_alteradas,
        personas_clasificadas=len(clasificadas),
        personas_riesgo_renal=len(en_riesgo),
        total_reportes=total_reportes,
        total_envios_exitosos=envios_ok,
        total_envios_fallidos=envios_fallidos,
        dias_promedio_entrega=dias_promedio,
        total_pruebas=total_determinaciones,
        total_pacientes=total_personas,
        porcentaje_fuera_rango=porcentaje,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=ResumenResponse)
async def get_dashboard_root(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soporte para la ruta raíz /api/dashboard (requerida por los tests API).
    """
    return await build_resumen(db)

@router.get("/resumen", response_model=ResumenResponse)
async def get_dashboard_resumen(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    KPIs del periodo (por fecha de toma). Cuenta personas, no determinaciones.
    """
    _validar_rango(desde, hasta)
    return await build_resumen(db, desde, hasta)

@router.get("/tendencia", response_model=List[TendenciaItem])
async def get_dashboard_tendencia(
    periodo: str = Query("mes", pattern="^(dia|semana|mes)$"),
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Personas atendidas por día, semana (inicia lunes) o mes. Una persona cuenta una
    vez por periodo aunque tenga varias pruebas.
    """
    _validar_rango(desde, hasta)
    stmt = (
        select(Resultado.paciente_id, Resultado.fecha_toma)
        .where(*_filtro_fecha_toma(desde, hasta))
        .distinct()
    )
    rows = (await db.execute(stmt)).all()

    def clave(d: date) -> str:
        if periodo == "dia":
            return d.isoformat()
        if periodo == "semana":
            return (d - timedelta(days=d.weekday())).isoformat()
        return d.strftime("%Y-%m")

    cubetas: dict[str, set] = {}
    for paciente_id, fecha in rows:
        cubetas.setdefault(clave(fecha), set()).add(paciente_id)

    return [
        TendenciaItem(periodo=k, cantidad=len(v))
        for k, v in sorted(cubetas.items())
    ]

@router.get("/anormales", response_model=List[AnormalesDistribucion])
async def get_dashboard_anormales(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Distribución de determinaciones por interpretación (informativo; el dashboard
    muestra el riesgo KDIGO por persona en /riesgo-kdigo).
    """
    _validar_rango(desde, hasta)
    stmt = (
        select(Resultado.interpretacion, func.count(Resultado.id))
        .where(*_filtro_fecha_toma(desde, hasta))
        .group_by(Resultado.interpretacion)
    )
    rows = (await db.execute(stmt)).all()
    return [AnormalesDistribucion(interpretacion=row[0] or "sin_interpretar", cantidad=row[1]) for row in rows]

@router.get("/riesgo-kdigo", response_model=RiesgoKdigoResponse)
async def get_dashboard_riesgo_kdigo(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Semáforo KDIGO: personas por categoría de TFG (G1–G5) × albuminuria (A1–A3).
    Cada persona cuenta una vez, con su determinación más reciente del periodo.
    Quienes solo tienen ACR (sin creatinina sérica) o solo TFG aparecen en las
    filas/columnas "Sin TFG" / "Sin ACR"; sin ninguna de las dos, en `sin_clasificar`.
    """
    _validar_rango(desde, hasta)
    return armar_matriz(await clasificar_pacientes(db, desde, hasta))

@router.get("/top-pruebas", response_model=List[TopPrueba])
async def get_dashboard_top_pruebas(
    limit: int = Query(10, ge=1),
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Pruebas más solicitadas, contadas en personas distintas.
    """
    _validar_rango(desde, hasta)
    stmt = (
        select(Prueba.codigo, Prueba.nombre, func.count(func.distinct(Resultado.paciente_id)).label("total"))
        .join(Resultado, Resultado.prueba_id == Prueba.id)
        .where(*_filtro_fecha_toma(desde, hasta))
        .group_by(Prueba.codigo, Prueba.nombre)
        .order_by(func.count(func.distinct(Resultado.paciente_id)).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [TopPrueba(codigo=row[0], nombre=row[1], cantidad=row[2]) for row in rows]


class ValorReciente(BaseModel):
    valor: Optional[float] = None
    valor_texto: Optional[str] = None
    unidad: str

class RecienteItem(BaseModel):
    paciente_id: int
    paciente: str
    fecha_toma: date
    valores: dict[str, ValorReciente]   # por código de prueba (ACR, CRE01, ALBOR, CRTS)
    riesgo: str
    color: str                          # green | yellow | orange | red | gray

class RecientesResponse(BaseModel):
    fecha: Optional[date] = None        # día mostrado; None si no hay resultados
    total_personas: int
    items: List[RecienteItem]

@router.get("/recientes", response_model=RecientesResponse)
async def get_dashboard_recientes(
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resultados del último día con tomas anterior a hoy (el "día anterior"), una fila por
    persona con sus valores renales juntos. Si no hay nada antes de hoy, usa el día más reciente.
    """
    hoy = date.today()
    dia = (await db.execute(
        select(func.max(Resultado.fecha_toma)).where(Resultado.fecha_toma < hoy)
    )).scalar()
    if dia is None:
        dia = (await db.execute(select(func.max(Resultado.fecha_toma)))).scalar()
    if dia is None:
        return RecientesResponse(fecha=None, total_personas=0, items=[])

    stmt = (
        select(Paciente, Prueba.codigo, Prueba.unidad, Resultado.valor, Resultado.valor_texto, Resultado.fecha_toma, Resultado.id)
        .join(Resultado, Resultado.paciente_id == Paciente.id)
        .join(Prueba, Prueba.id == Resultado.prueba_id)
        .where(Resultado.fecha_toma == dia, Prueba.codigo.in_(CODIGOS_RENALES))
        .order_by(Resultado.id)
    )
    filas = (await db.execute(stmt)).all()

    pacientes: dict[int, Paciente] = {}
    ultimos: dict[int, dict] = {}
    unidades: dict[int, dict] = {}
    orden: dict[int, int] = {}
    for paciente, codigo, unidad, val, texto, fecha, rid in filas:
        codigo = codigo.upper()
        pacientes[paciente.id] = paciente
        ultimos.setdefault(paciente.id, {})[codigo] = (float(val) if val is not None else None, texto, fecha)
        unidades.setdefault(paciente.id, {})[codigo] = unidad
        orden[paciente.id] = max(orden.get(paciente.id, 0), rid)

    ids = sorted(ultimos, key=lambda pid: orden[pid], reverse=True)
    items = []
    for pid in ids[:limit]:
        clas = clasificar_persona(pacientes[pid], ultimos[pid])
        items.append(RecienteItem(
            paciente_id=pid,
            paciente=nombre_completo_paciente(pacientes[pid]),
            fecha_toma=dia,
            valores={
                cod: ValorReciente(valor=v[0], valor_texto=v[1], unidad=unidades[pid][cod])
                for cod, v in ultimos[pid].items()
            },
            riesgo=clas["riesgo"],
            color=clas["color"],
        ))
    return RecientesResponse(fecha=dia, total_personas=len(ids), items=items)


# ── Mapa de Pacientes ─────────────────────────────────────────────────────────

class MapaHexbinResponse(BaseModel):
    tamizados: List[dict]
    positivos: List[dict]

class GeocodeResultResponse(BaseModel):
    geocodificados: int
    fallidos: int
    sin_geocodificar_restantes: int

@router.get("/mapa-hexbin", response_model=MapaHexbinResponse)
async def get_mapa_hexbin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna los puntos geocodificados de pacientes en Aguascalientes,
    separados en 'tamizados' (todos) y 'positivos' (TFG < 60 o ACR > 30).
    """
    from sqlalchemy.orm import selectinload
    
    # Traer pacientes geocodificados de AGS con sus resultados
    stmt = (
        select(Paciente)
        .options(selectinload(Paciente.resultados).selectinload(Resultado.prueba))
        .where(
            and_(
                Paciente.lat.isnot(None),
                Paciente.lon.isnot(None),
                or_(
                    Paciente.estado_residencia.ilike("%aguascalientes%"),
                    Paciente.municipio_residencia.ilike("%aguascalientes%"),
                )
            )
        )
    )
    result = await db.execute(stmt)
    pacientes = result.scalars().unique().all()

    tamizados = []
    positivos = []

    for p in pacientes:
        if not p.lat or not p.lon:
            continue
            
        pt = {"lat": float(p.lat), "lon": float(p.lon)}
        tamizados.append(pt)
        
        # Evaluar positividad
        is_positive = False
        
        # Edad en años
        edad = None
        if p.fecha_nacimiento:
            hoy = date.today()
            edad = hoy.year - p.fecha_nacimiento.year - ((hoy.month, hoy.day) < (p.fecha_nacimiento.month, p.fecha_nacimiento.day))
            
        for r in p.resultados:
            if not r.valor:
                continue
                
            val = float(r.valor)
            codigo = r.prueba.codigo.upper()
            
            # Condición 1: ACR > 30
            if codigo == "ACR" and val > 30:
                is_positive = True
                break
                
            # Condición 2: eGFR < 60 (evaluada a partir de Creatinina Sérica)
            if codigo == "CRTS" and edad is not None:
                egfr = None
                is_female = (p.sexo == "F")
                
                if edad < 18:
                    # Schwartz 2009 bedside
                    # asumiendo p.estatura en cm
                    if p.estatura:
                        egfr = (0.413 * float(p.estatura)) / val
                else:
                    # CKD-EPI 2021
                    k = 0.7 if is_female else 0.9
                    a = -0.241 if is_female else -0.302
                    
                    scr_k = val / k
                    min_val = scr_k if scr_k < 1 else 1
                    max_val = scr_k if scr_k > 1 else 1
                    
                    egfr = 142 * (min_val ** a) * (max_val ** -1.200) * (0.9938 ** edad)
                    if is_female:
                        egfr *= 1.012
                        
                if egfr is not None and egfr < 60:
                    is_positive = True
                    break
                    
        if is_positive:
            positivos.append(pt)

    return MapaHexbinResponse(tamizados=tamizados, positivos=positivos)


@router.post("/geocodificar", response_model=GeocodeResultResponse)
async def geocodificar_pacientes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Geocodifica en batch los pacientes de Aguascalientes que aún no tienen
    coordenadas, en lotes acotados para no exceder el timeout del proxy.

    Usa Nominatim local (servicio del stack) y, como fallback, Google
    Geocoding API. Ver app/services/geocoding.py.

    Solo usuarios autenticados pueden disparar este proceso.
    """
    from app.services.geocoding import geocode_batch

    # Lote acotado: Nominatim local es rápido, pero el fallback a Google añade
    # latencia. GEOCODING_BATCH_SIZE mantiene la respuesta bajo el proxy_read_timeout.
    batch_size = get_settings().GEOCODING_BATCH_SIZE
    stmt = select(Paciente).where(
        and_(
            Paciente.lat.is_(None),
            or_(
                Paciente.estado_residencia.ilike("%aguascalientes%"),
                Paciente.municipio_residencia.ilike("%aguascalientes%"),
            )
        )
    ).limit(batch_size)
    result = await db.execute(stmt)
    pacientes = result.scalars().all()

    if not pacientes:
        # Contar cuántos ya tienen geocodificación
        stmt_total = select(func.count(Paciente.id)).where(
            and_(
                Paciente.lat.isnot(None),
                or_(
                    Paciente.estado_residencia.ilike("%aguascalientes%"),
                    Paciente.municipio_residencia.ilike("%aguascalientes%"),
                )
            )
        )
        total_ok = (await db.execute(stmt_total)).scalar() or 0
        return GeocodeResultResponse(geocodificados=0, fallidos=0, sin_geocodificar_restantes=0)

    geocodificados, fallidos = await geocode_batch(pacientes, db)
    await db.commit()

    # Contar cuántos quedaron sin geocodificar en Aguascalientes
    stmt_restantes = select(func.count(Paciente.id)).where(
        and_(
            Paciente.lat.is_(None),
            or_(
                Paciente.estado_residencia.ilike("%aguascalientes%"),
                Paciente.municipio_residencia.ilike("%aguascalientes%"),
            )
        )
    )
    restantes = (await db.execute(stmt_restantes)).scalar() or 0

    return GeocodeResultResponse(
        geocodificados=geocodificados,
        fallidos=fallidos,
        sin_geocodificar_restantes=restantes,
    )
