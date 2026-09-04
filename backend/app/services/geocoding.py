"""
Servicio de geocodificación de direcciones para el mapa de pacientes.

Estrategia, en orden:
  1. Nominatim LOCAL  -> contenedor `nominatim` del stack (rápido, sin rate
     limit, cobertura Aguascalientes + buffer). Consultas estructuradas
     progresivas: struct+CP -> struct -> texto libre -> texto libre mínimo ->
     colonia. Se acepta si el resultado es de nivel calle o mejor.
  2. Google Geocoding API -> sólo si Nominatim no alcanzó nivel calle o no
     devolvió nada. Requiere GOOGLE_GEOCODING_API_KEY; si no está, se omite.
  3. Mejor resultado parcial de Nominatim (nivel colonia) como último recurso.

Config (app.config.Settings):
  NOMINATIM_BASE_URL, GOOGLE_GEOCODING_API_KEY, GEOCODING_GOOGLE_SLEEP,
  GEOCODING_CONCURRENCY
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Umbral de calidad (place_rank de Nominatim) ──────────────────────────────
#   >= 30  número de casa exacto
#   >= 26  calle (aceptable para el mapa)
#   >= 16  colonia / localidad
MIN_ACCEPT_RANK = 26

# ── Caja de cordura: Aguascalientes + estados vecinos ────────────────────────
# Sólo descarta resultados claramente equivocados (otro país, (0,0), etc.).
SANE_LAT_MIN, SANE_LAT_MAX = 20.0, 24.0
SANE_LON_MIN, SANE_LON_MAX = -104.5, -100.0

_HTTP_HEADERS = {"User-Agent": "LabResultados/geocoder (interno)"}

_COL_KW = re.compile(
    r"\b(col\.?|colonia|fracc\.?|fraccionamiento|barrio|priv\.?|privada|"
    r"unidad\s+hab\.?|infonavit)\b",
    re.I,
)
_ESTADOS_VECINOS = (
    ("zacateca", "Zacatecas"),
    ("jalisco", "Jalisco"),
    ("guanajuato", "Guanajuato"),
    ("nayarit", "Nayarit"),
    ("durango", "Durango"),
    ("san luis", "San Luis Potosí"),
)


def _clean(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("#", " ")).strip(" ,.")


def _sane(lat: float, lon: float) -> bool:
    return SANE_LAT_MIN <= lat <= SANE_LAT_MAX and SANE_LON_MIN <= lon <= SANE_LON_MAX


def _split_domicilio(domicilio: str) -> Tuple[str, str]:
    """Separa '(calle y número, colonia)' con una heurística sencilla."""
    d = _clean(domicilio)
    if not d:
        return "", ""
    m = _COL_KW.search(d)
    if m:
        return d[: m.start()].strip(" ,") or d, d[m.end():].strip(" ,")
    m = re.match(r"^(.*?\d+\s?[A-Za-z]?)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ].+)$", d)
    if m and len(m.group(2).split()) >= 2:
        return m.group(1).strip(" ,"), m.group(2).strip(" ,")
    return d, ""


def _normalize_estado(estado: Optional[str]) -> str:
    low = _clean(estado).lower()
    for kw, name in _ESTADOS_VECINOS:
        if kw in low:
            return name
    return "Aguascalientes"


def _clean_cp(cp: Optional[str]) -> str:
    m = re.search(r"\b(\d{5})\b", _clean(cp))
    return m.group(1) if m else ""


# ── Nominatim ───────────────────────────────────────────────────────────────

async def _nominatim_search(client: httpx.AsyncClient, params: dict) -> Optional[dict]:
    base = settings.NOMINATIM_BASE_URL.rstrip("/")
    common = {"format": "jsonv2", "limit": 1, "addressdetails": 1, "countrycodes": "mx"}
    try:
        resp = await client.get(f"{base}/search", params={**common, **params})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nominatim error %s: %s", params, exc)
        return None
    if not data:
        return None
    hit = data[0]
    try:
        lat, lon = float(hit["lat"]), float(hit["lon"])
    except (KeyError, ValueError, TypeError):
        return None
    if not _sane(lat, lon):
        return None
    return {"lat": lat, "lon": lon, "rank": int(hit.get("place_rank", 0))}


async def _try_nominatim(
    client: httpx.AsyncClient,
    calle: str,
    colonia: str,
    municipio: str,
    estado: str,
    cp: str,
) -> Tuple[Optional[dict], Optional[dict]]:
    """Devuelve (resultado_aceptado, mejor_parcial)."""
    attempts: list[dict] = []
    if calle and cp:
        attempts.append({"street": calle, "city": municipio, "state": estado, "postalcode": cp})
    if calle:
        attempts.append({"street": calle, "city": municipio, "state": estado})
    q1 = ", ".join(p for p in [calle, colonia, municipio, estado] if p)
    if q1:
        attempts.append({"q": q1})
    q2 = ", ".join(p for p in [calle, municipio, estado] if p)
    if q2 and q2 != q1:
        attempts.append({"q": q2})
    if colonia and municipio:
        attempts.append({"q": f"{colonia}, {municipio}, {estado}"})

    best: Optional[dict] = None
    for params in attempts:
        res = await _nominatim_search(client, params)
        if not res:
            continue
        if res["rank"] >= MIN_ACCEPT_RANK:
            return res, best
        if best is None or res["rank"] > best["rank"]:
            best = res
    return None, best


# ── Google ──────────────────────────────────────────────────────────────────

async def _try_google(client: httpx.AsyncClient, query: str) -> Optional[dict]:
    key = settings.GOOGLE_GEOCODING_API_KEY
    if not key or not query:
        return None
    try:
        resp = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": query, "key": key, "region": "mx", "language": "es"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google error '%s': %s", query, exc)
        return None
    status = data.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK" or not data.get("results"):
        logger.warning("Google status=%s msg=%s", status, data.get("error_message"))
        return None
    geom = data["results"][0]["geometry"]
    lat, lon = float(geom["location"]["lat"]), float(geom["location"]["lng"])
    if not _sane(lat, lon):
        return None
    return {"lat": lat, "lon": lon, "loc_type": geom.get("location_type", "APPROXIMATE")}


# ── API pública del módulo ──────────────────────────────────────────────────

async def geocode_address(
    domicilio: Optional[str],
    codigo_postal: Optional[str],
    municipio: Optional[str],
    estado: Optional[str],
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """Geocodifica una dirección. Devuelve (lat, lon) o (None, None)."""
    calle, colonia = _split_domicilio(domicilio or "")
    municipio_c = _clean(municipio) or "Aguascalientes"
    estado_c = _normalize_estado(estado)
    cp_c = _clean_cp(codigo_postal)

    if not calle and not colonia and not cp_c:
        return None, None

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=15.0, headers=_HTTP_HEADERS)
    try:
        accepted, best = await _try_nominatim(client, calle, colonia, municipio_c, estado_c, cp_c)
        if accepted:
            logger.info(
                "geocode nominatim: '%s' -> (%.6f, %.6f) rank%d",
                calle or colonia or municipio_c, accepted["lat"], accepted["lon"], accepted["rank"],
            )
            return round(accepted["lat"], 6), round(accepted["lon"], 6)

        google_query = ", ".join(
            p for p in [calle, colonia, municipio_c, estado_c, cp_c, "México"] if p
        )
        g = await _try_google(client, google_query)
        if settings.GOOGLE_GEOCODING_API_KEY:
            await asyncio.sleep(settings.GEOCODING_GOOGLE_SLEEP)
        if g:
            logger.info(
                "geocode google: '%s' -> (%.6f, %.6f) %s",
                google_query, g["lat"], g["lon"], g["loc_type"],
            )
            return round(g["lat"], 6), round(g["lon"], 6)

        if best:
            logger.info(
                "geocode nominatim parcial: -> (%.6f, %.6f) rank%d",
                best["lat"], best["lon"], best["rank"],
            )
            return round(best["lat"], 6), round(best["lon"], 6)

        return None, None
    finally:
        if own_client:
            await client.aclose()


async def geocode_batch(pacientes: list, session) -> Tuple[int, int]:
    """Geocodifica una lista de pacientes en paralelo (acotado) y persiste
    lat/lon/geocoded_at. Devuelve (geocodificados, fallidos)."""
    sem = asyncio.Semaphore(max(1, settings.GEOCODING_CONCURRENCY))

    async with httpx.AsyncClient(timeout=15.0, headers=_HTTP_HEADERS) as client:
        async def _one(p):
            async with sem:
                return await geocode_address(
                    p.domicilio, p.codigo_postal, p.municipio_residencia,
                    p.estado_residencia, client=client,
                )

        resultados = await asyncio.gather(
            *(_one(p) for p in pacientes), return_exceptions=True
        )

    geocodificados = 0
    fallidos = 0
    ahora = datetime.now(timezone.utc)
    for paciente, res in zip(pacientes, resultados):
        if isinstance(res, BaseException) or res is None:
            if isinstance(res, BaseException):
                logger.warning(
                    "geocode_batch excepción para paciente %s: %s",
                    getattr(paciente, "id", "?"), res,
                )
            fallidos += 1
            continue
        lat, lon = res
        if lat is not None and lon is not None:
            paciente.lat = lat
            paciente.lon = lon
            paciente.geocoded_at = ahora
            geocodificados += 1
        else:
            fallidos += 1

    await session.flush()
    return geocodificados, fallidos
