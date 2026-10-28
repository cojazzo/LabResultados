"""
ACR censurado: albuminuria fuera del rango de la tira (UC-1000 / MEDITAPE UC-12S).

La tira mide albúmina hasta 150 mg/L; arriba de eso el equipo escribe "Over" y no se puede
calcular un ACR exacto. Pero como ALB > 150 mg/L, el ACR tiene una cota inferior conocida:

    ACR > 150 mg/L ÷ CRE mg/dL × 100          (ej. CRE 100 → ACR > 150 mg/g)

Se guarda esa cota como valor del ACR con valor_texto ">X" para que todo lo demás (interpretación,
dashboard, exportaciones) la trate como positiva (≥ A2) sin hacerla pasar por un valor exacto.
Cuando llega la albúmina cuantitativa (Vitros) el ACR exacto reemplaza a la cota.
"""

from typing import Optional

ALB_TECHO_TIRA = 150.0    # mg/L, límite superior de la tira para albúmina
CRE_DILUIDA_MAX = 10.0    # mg/dL, la tira marca "dilute": la muestra no sirve para el cociente
ACR_A3_MIN = 300.0        # mg/g, KDIGO A3 es > 300

OBS_COTA = (
    "ALB fuera del rango de la tira (>{alb:g} mg/L), CRE {cre:g} mg/dL: ACR mayor a {cota:g} mg/g "
    "(cota mínima, no es un valor exacto). Positivo, pendiente de confirmar con albúmina cuantitativa."
)


def cota_acr(cre_mg_dl: Optional[float]) -> Optional[float]:
    """Cota inferior del ACR (mg/g) cuando la albúmina está en 'over'; None si no se puede acotar."""
    if cre_mg_dl is None or cre_mg_dl <= CRE_DILUIDA_MAX:
        return None
    return round(ALB_TECHO_TIRA / cre_mg_dl * 100, 1)


def texto_cota(cota: float) -> str:
    return f">{cota:g}"


def es_cota(valor_texto: Optional[str]) -> bool:
    """True si el valor_texto de un ACR es una cota inferior (">X")."""
    return bool(valor_texto) and valor_texto.strip().startswith(">")


def observacion_cota(cre_mg_dl: float, cota: float) -> str:
    return OBS_COTA.format(alb=ALB_TECHO_TIRA, cre=cre_mg_dl, cota=cota)
