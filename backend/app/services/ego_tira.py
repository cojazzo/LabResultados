"""
Examen químico del EGO a partir del CSV del UC-1000 (tira MEDITAPE 12S).

Las columnas se localizan por encabezado (fila 0 = parámetro, fila 1 = subcolumna), no por
posición. Cada parámetro trae "Flag" (grado: " -", "+-", "1+", "normal", o el valor en pH y
densidad) y "Conc" (concentración). La marca "*" del equipo no se usa: el sistema no interpreta.

Los valores se precargan en `examenes_orina` sin capturista. El EGO solo se reporta (folio y PDF) cuando
una persona lo guarda en la pantalla de captura (ver app/routes/ego.py).
"""

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExamenOrina
from app.utils.ego import CLAVES_QUIMICO

FUENTE_TIRA = "tira_uc1000"

# campo del EGO -> (parámetro del UC-1000, incluir concentración)
# La concentración se agrega solo cuando sus unidades coinciden con las del formato
# (mg/dL; Leu/µL en leucocitos). Sangre se reporta solo con su grado: el formato usa Eri/µL.
MAPEO = {
    "urobilinogeno": ("URO", True),
    "sangre": ("BLD", False),
    "bilirrubina": ("BIL", True),
    "cetonas": ("KET", True),
    "glucosa": ("GLU", True),
    "proteinas": ("PRO", True),
    "ph": ("pH", False),
    "nitritos": ("NIT", False),
    "leucocitos_esterasa": ("LEU", True),
    "densidad": ("S.G", False),
}

_GRADOS = {"-": "Negativo", "normal": "Normal", "+-": "±"}


def mapa_columnas(fila_grupos: list[str], fila_sub: list[str]) -> dict[tuple[str, str], int]:
    """(parámetro, subcolumna) -> índice, p. ej. ("GLU", "Flag") -> 36."""
    mapa, grupo = {}, None
    for i, sub in enumerate(fila_sub):
        if i < len(fila_grupos) and fila_grupos[i].strip():
            grupo = fila_grupos[i].strip()
        if grupo and sub.strip():
            mapa.setdefault((grupo, sub.strip()), i)
    return mapa


def _celda(row: list[str], idx: Optional[int]) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip().lstrip("*").strip()


def extraer_quimico(row: list[str], columnas: dict) -> dict[str, str]:
    """Valores del examen químico de una fila; omite los parámetros vacíos o ausentes."""
    valores = {}
    for campo, (param, con_conc) in MAPEO.items():
        flag = _celda(row, columnas.get((param, "Flag")))
        if not flag:
            continue
        if param == "NIT":
            texto = "Positivo" if flag.startswith("+") else _GRADOS.get(flag, flag)
        else:
            texto = _GRADOS.get("normal" if flag.lower() == "normal" else flag, flag)
        conc = _celda(row, columnas.get((param, "Conc"))) if con_conc else ""
        if conc and texto not in ("Negativo", "Normal"):
            texto = f"{texto} ({conc})"
        valores[campo] = texto
    return valores


async def precargar_quimico(
    db: AsyncSession, paciente_id: int, fecha_toma: date, valores: dict[str, str]
) -> bool:
    """
    Guarda el examen químico de la tira en el EGO de esa persona y fecha.
    No pisa un examen químico que el químico haya capturado o corregido a mano.
    """
    if not valores:
        return False
    examen = (await db.execute(
        select(ExamenOrina).where(ExamenOrina.paciente_id == paciente_id, ExamenOrina.fecha_toma == fecha_toma)
    )).scalar_one_or_none()
    if examen is None:
        examen = ExamenOrina(paciente_id=paciente_id, fecha_toma=fecha_toma)
        db.add(examen)
    elif examen.quimico_fuente != FUENTE_TIRA and any(getattr(examen, c) for c in CLAVES_QUIMICO):
        return False
    for campo in CLAVES_QUIMICO:
        setattr(examen, campo, valores.get(campo))
    examen.quimico_fuente = FUENTE_TIRA
    return True
