"""
Servicio de geocodificación basado en Photon Komoot (OpenStreetMap).

Usamos Photon porque Nominatim es muy estricto con el rate limit y 
bloquea IPs de servidores (429/403) cuando se hacen geocodificaciones masivas.
"""

import asyncio
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
PHOTON_URL = "https://photon.komoot.io/api/"
USER_AGENT = "LabResultados/1.0 (laboratorio clinico interno; contacto@lab.local)"

# Bounding box de Aguascalientes (estado), aprox.
BBOX_LAT_MIN = 21.5
BBOX_LAT_MAX = 22.5
BBOX_LON_MIN = -102.8
BBOX_LON_MAX = -101.6

# Pausa mínima entre solicitudes (Photon es más permisivo, 0.5s está bien)
RATE_LIMIT_SECONDS = 0.5


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
    Geocodifica una dirección usando Photon Komoot.
    """
    import re
    queries_to_try = []

    if domicilio and codigo_postal:
        queries_to_try.append(", ".join(p for p in [domicilio, codigo_postal, municipio, estado, "México"] if p))
        
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

    if codigo_postal:
        queries_to_try.append(", ".join(p for p in [codigo_postal, municipio, estado, "México"] if p))

    queries_to_try.append(", ".join(p for p in [municipio, estado, "México"] if p))

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for query in queries_to_try:
            params = {
                "q": query,
                "limit": 1,
                "bbox": f"{BBOX_LON_MIN},{BBOX_LAT_MIN},{BBOX_LON_MAX},{BBOX_LAT_MAX}",
            }
            
            try:
                response = await client.get(PHOTON_URL, params=params, headers=headers)
                response.raise_for_status()
                results = response.json()

                if results.get("features"):
                    # Photon retorna [lon, lat]
                    lon = float(results["features"][0]["geometry"]["coordinates"][0])
                    lat = float(results["features"][0]["geometry"]["coordinates"][1])

                    if _within_aguascalientes(lat, lon):
                        logger.info("Geocodificado: '%s' → (%.6f, %.6f)", query, lat, lon)
                        return lat, lon
            except Exception as exc:
                logger.warning("Photon error para '%s': %s", query, exc)
            
            await asyncio.sleep(RATE_LIMIT_SECONDS)

    return None, None


async def geocode_batch(
    pacientes: list,
    session,
) -> Tuple[int, int]:
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

    await session.flush()
    return geocodificados, fallidos
