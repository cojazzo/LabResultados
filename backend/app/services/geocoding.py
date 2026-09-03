"""
Servicio de geocodificación basado en Nominatim (OpenStreetMap).

Política de uso de Nominatim:
- Máximo 1 solicitud por segundo.
- Obligatorio: User-Agent identificador de la aplicación.
- Solo para datos NO comerciales. LabResultados es uso interno de laboratorio.

El geocoding se ejecuta en batch desde el endpoint /dashboard/geocodificar
y los resultados se almacenan en la BD para no re-consultar.
"""

import asyncio
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "LabResultados/1.0 (laboratorio clinico interno; contacto@lab.local)"

# Bounding box de Aguascalientes (estado), aprox.
# lat: 21.5 – 22.5 N  |  lon: -102.8 – -101.6 O
BBOX_LAT_MIN = 21.5
BBOX_LAT_MAX = 22.5
BBOX_LON_MIN = -102.8
BBOX_LON_MAX = -101.6

# Pausa mínima entre solicitudes (política de Nominatim: 1 req/s)
NOMINATIM_RATE_LIMIT_SECONDS = 1.1


def _within_aguascalientes(lat: float, lon: float) -> bool:
    """Verifica que las coordenadas estén dentro del bounding box de Aguascalientes."""
    return (
        BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX
        and BBOX_LON_MIN <= lon <= BBOX_LON_MAX
    )


async def geocode_address(
    domicilio: Optional[str],
    codigo_postal: Optional[str],
    municipio: Optional[str],
    estado: Optional[str],
) -> Tuple[Optional[float], Optional[float]]:
    """
    Geocodifica una dirección usando Nominatim con sistema de reintentos decrecientes.
    Retorna (lat, lon) si tiene éxito y las coordenadas están dentro de
    Aguascalientes. Retorna (None, None) en cualquier fallo.
    """
    import re
    queries_to_try = []

    # 1. Dirección completa con CP (ideal)
    if domicilio and codigo_postal:
        queries_to_try.append(", ".join(p for p in [domicilio, codigo_postal, municipio, estado, "México"] if p))
        
    # 2. Dirección completa sin CP (por si el CP es erróneo)
    if domicilio:
        queries_to_try.append(", ".join(p for p in [domicilio, municipio, estado, "México"] if p))
        
        clean_dom = re.sub(r'#\s*', '', domicilio)
        match = re.search(r'^([a-zA-ZñÑáéíóúÁÉÍÓÚ\s0-9\.oOaA]+\s\d+)', clean_dom)
        if match:
            clean_dom = match.group(1).strip()
            
        if clean_dom and clean_dom != domicilio:
            if codigo_postal:
                queries_to_try.append(", ".join(p for p in [clean_dom, codigo_postal, municipio, estado, "México"] if p))
            queries_to_try.append(", ".join(p for p in [clean_dom, municipio, estado, "México"] if p))

    # 3. Fallback al Código Postal (Si falla la calle, mapear a la colonia/CP)
    if codigo_postal:
        queries_to_try.append(", ".join(p for p in [codigo_postal, municipio, estado, "México"] if p))

    # 4. Fallback al Municipio (aglomera, pero peor es nada)
    queries_to_try.append(", ".join(p for p in [municipio, estado, "México"] if p))

    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for query in queries_to_try:
                params = {
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "mx",
                    "bounded": 1,
                    "viewbox": f"{BBOX_LON_MIN},{BBOX_LAT_MAX},{BBOX_LON_MAX},{BBOX_LAT_MIN}",
                }
                
                response = await client.get(NOMINATIM_URL, params=params, headers=headers)
                response.raise_for_status()
                results = response.json()

                if results:
                    lat = float(results[0]["lat"])
                    lon = float(results[0]["lon"])

                    if _within_aguascalientes(lat, lon):
                        logger.info("Geocodificado: '%s' → (%.6f, %.6f)", query, lat, lon)
                        return lat, lon
                
                # Respetar rate limit de Nominatim antes de intentar con el siguiente fallback
                await asyncio.sleep(NOMINATIM_RATE_LIMIT_SECONDS)

        logger.debug("Nominatim: agotados todos los intentos para '%s'", domicilio)
        return None, None

    except httpx.HTTPError as exc:
        logger.warning("Nominatim HTTP error para '%s': %s", query, exc)
        return None, None
    except Exception as exc:
        logger.error("Error inesperado geocodificando '%s': %s", query, exc)
        return None, None


async def geocode_batch(
    pacientes: list,
    session,
) -> Tuple[int, int]:
    """
    Geocodifica en batch una lista de objetos Paciente que aún no tienen
    coordenadas. Actualiza la BD directamente vía la sesión recibida.

    Respeta el rate limit de Nominatim con una pausa entre solicitudes.

    Retorna (geocodificados, fallidos).
    """
    from datetime import datetime, timezone

    geocodificados = 0
    fallidos = 0

    for paciente in pacientes:
        lat, lon = await geocode_address(
            domicilio=paciente.domicilio,
            codigo_postal=paciente.codigo_postal,
            municipio=paciente.municipio_residencia,
            estado=paciente.estado_residencia,
        )

        if lat is not None and lon is not None:
            paciente.lat = lat
            paciente.lon = lon
            paciente.geocoded_at = datetime.now(timezone.utc)
            geocodificados += 1
        else:
            fallidos += 1

        # Respetar rate limit de Nominatim entre cada solicitud
        await asyncio.sleep(NOMINATIM_RATE_LIMIT_SECONDS)

    await session.flush()
    return geocodificados, fallidos
