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
    municipio: Optional[str],
    estado: Optional[str],
) -> Tuple[Optional[float], Optional[float]]:
    """
    Geocodifica una dirección usando Nominatim.

    Retorna (lat, lon) si tiene éxito y las coordenadas están dentro de
    Aguascalientes. Retorna (None, None) en cualquier fallo.
    """
    # Construir query: calle/colonia + municipio + estado + país
    partes = [p for p in [domicilio, municipio, estado, "México"] if p]
    if not partes:
        return None, None

    query = ", ".join(partes)

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "mx",
        "bounded": 1,
        "viewbox": f"{BBOX_LON_MIN},{BBOX_LAT_MAX},{BBOX_LON_MAX},{BBOX_LAT_MIN}",
    }

    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()

        if not results:
            logger.debug("Nominatim: sin resultados para '%s'", query)
            return None, None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])

        if not _within_aguascalientes(lat, lon):
            logger.debug(
                "Nominatim: resultado fuera de Aguascalientes para '%s' → (%s, %s)",
                query, lat, lon,
            )
            return None, None

        logger.info("Geocodificado: '%s' → (%.6f, %.6f)", query, lat, lon)
        return lat, lon

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
