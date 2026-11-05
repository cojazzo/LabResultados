"""
Clasificación de riesgo renal KDIGO por persona, para el dashboard.

No define criterios clínicos propios: reutiliza `calculate_egfr` y `get_kdigo_classification`
del generador de reportes, de modo que el dashboard y el PDF del paciente clasifiquen igual.

Cada persona cuenta UNA vez, con su determinación más reciente de cada prueba
(CRTS, CRE01, ALBOR, ACR) dentro del periodo filtrado.
"""

from collections import Counter
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Paciente, Prueba, Resultado
from app.services.pdf_generator import calculate_egfr, get_kdigo_classification, resolve_sex
from app.utils.acr import es_cota

CODIGOS_RENALES = ("CRTS", "CRE01", "ALBOR", "ACR")

FILAS_G = ["G1", "G2", "G3a", "G3b", "G4", "G5", "Sin TFG"]
COLUMNAS_A = ["A1", "A2", "A3", "Sin ACR"]

# Valores representativos para obtener, desde la misma función KDIGO, el color de cada celda.
_EGFR_REPRESENTATIVO = {"G1": 100.0, "G2": 75.0, "G3a": 52.0, "G3b": 38.0, "G4": 20.0, "G5": 10.0}
_ACR_REPRESENTATIVO = {"A1": 10.0, "A2": 100.0, "A3": 500.0}


def _edad_en(dob: date, ref: date) -> int:
    # Mismo ajuste que el reporte PDF: años futuros mal capturados (2090 en vez de 1990).
    if dob.year > datetime.now().year:
        dob = dob.replace(year=dob.year - 100)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def clasificar_persona(paciente: Paciente, ultimos: dict) -> dict:
    """
    `ultimos` mapea código de prueba -> (valor_float | None, valor_texto, fecha_toma).
    Devuelve eGFR, ACR y la categoría KDIGO (g, a, color, riesgo).
    """
    def valor(codigo):
        item = ultimos.get(codigo)
        return item[0] if item else None

    acr = valor("ACR")
    acr_cota = bool(ultimos.get("ACR")) and es_cota(ultimos["ACR"][1])
    albor, cre01 = valor("ALBOR"), valor("CRE01")
    if acr is None and albor is not None and cre01 is not None and cre01 > 0:
        acr = albor / cre01 * 100

    egfr = None
    crts = valor("CRTS")
    # Sin fecha de nacimiento no se puede estimar la TFG; no se asume una edad.
    if crts is not None and crts > 0 and paciente.fecha_nacimiento:
        edad = _edad_en(paciente.fecha_nacimiento, ultimos["CRTS"][2])
        estatura = float(paciente.estatura) if paciente.estatura is not None else None
        egfr, _ = calculate_egfr(crts, edad, resolve_sex(paciente), estatura)

    kdigo = get_kdigo_classification(egfr, acr, acr_cota)
    return {"egfr": egfr, "acr": acr, "acr_cota": acr_cota, **kdigo}


async def clasificar_pacientes(
    db: AsyncSession, desde: Optional[date] = None, hasta: Optional[date] = None
) -> list[dict]:
    """Una clasificación por persona con resultados renales en el periodo."""
    condiciones = [Prueba.codigo.in_(CODIGOS_RENALES)]
    if desde:
        condiciones.append(Resultado.fecha_toma >= desde)
    if hasta:
        condiciones.append(Resultado.fecha_toma <= hasta)

    stmt = (
        select(Paciente, Prueba.codigo, Resultado.valor, Resultado.valor_texto, Resultado.fecha_toma)
        .join(Resultado, Resultado.paciente_id == Paciente.id)
        .join(Prueba, Prueba.id == Resultado.prueba_id)
        .where(and_(*condiciones))
        .order_by(Resultado.fecha_toma, Resultado.id)  # el más reciente queda al final y gana
    )
    filas = (await db.execute(stmt)).all()

    pacientes: dict[int, Paciente] = {}
    ultimos: dict[int, dict] = {}
    for paciente, codigo, val, texto, fecha in filas:
        pacientes[paciente.id] = paciente
        ultimos.setdefault(paciente.id, {})[codigo.upper()] = (
            float(val) if val is not None else None, texto, fecha,
        )

    return [clasificar_persona(pacientes[pid], datos) for pid, datos in ultimos.items()]


def _color_celda(g: str, a: str) -> str:
    egfr = _EGFR_REPRESENTATIVO.get(g)
    acr = _ACR_REPRESENTATIVO.get(a)
    if egfr is None and acr is None:
        return "gray"
    return get_kdigo_classification(egfr, acr)["color"]


def armar_matriz(clasificaciones: list[dict]) -> dict:
    """Cuenta personas por celda G × A y por nivel de riesgo."""
    por_celda: Counter = Counter()
    por_color: Counter = Counter()
    sin_clasificar = 0

    for c in clasificaciones:
        g = c["g_cat"] or "Sin TFG"
        a = c["a_cat"] or "Sin ACR"
        if g == "Sin TFG" and a == "Sin ACR":
            sin_clasificar += 1
            continue
        por_celda[(g, a)] += 1
        if c["g_cat"] and c["a_cat"]:
            por_color[c["color"]] += 1

    celdas = [
        {"g": g, "a": a, "cantidad": por_celda[(g, a)], "color": _color_celda(g, a)}
        for g in FILAS_G
        for a in COLUMNAS_A
        if not (g == "Sin TFG" and a == "Sin ACR")
    ]
    return {
        "filas": FILAS_G,
        "columnas": COLUMNAS_A,
        "celdas": celdas,
        "total_personas": len(clasificaciones),
        "sin_clasificar": sin_clasificar,
        # Solo las personas con TFG y ACR entran al semáforo completo.
        "completas": sum(por_color.values()),
        "por_riesgo": {
            "bajo": por_color["green"],
            "moderado": por_color["yellow"],
            "alto": por_color["orange"],
            "muy_alto": por_color["red"],
        },
    }
