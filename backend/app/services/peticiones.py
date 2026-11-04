"""
Peticiones del servicio externo: vínculo ID de petición (8 dígitos) -> paciente.

El UC-1000 identifica las muestras de orina con "<modificador 2 dígitos><petición 8 dígitos>" (ej. 1799922201).
Si a la persona se le pidió creatinina en Vitros, el Excel del Vitros registra la petición ("Petición No. N" en las
observaciones de sus resultados). Si solo se hizo la tira, no hay Vitros y el vínculo se registra aquí, a mano o por API.
"""
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Paciente, Peticion

_PETICION_RE = re.compile(r"^(?:\d{2})?(\d{8})$")


def normalizar_peticion(valor) -> Optional[str]:
    """'99922201' o '1799922201' (con modificador) -> '99922201'; None si no tiene ese formato."""
    if valor is None:
        return None
    m = _PETICION_RE.match(re.sub(r"\.0+$", "", re.sub(r"\s+", "", str(valor))))   # Excel puede dar "99922201.0"
    return m.group(1) if m else None


async def paciente_por_peticion(db: AsyncSession, id_peticion: str) -> Optional[Paciente]:
    res = await db.execute(
        select(Paciente).join(Peticion, Peticion.paciente_id == Paciente.id).where(Peticion.id_peticion == id_peticion))
    return res.scalar_one_or_none()


async def vincular_peticion(db: AsyncSession, id_peticion: str, paciente: Paciente, fuente: str = "manual") -> str:
    """
    Vincula la petición al paciente (sin confirmar la transacción). Devuelve:
      "vinculada"       -> se creó el vínculo
      "ya_vinculada"    -> ya estaba vinculada a este mismo paciente
      "conflicto"       -> ya está vinculada a OTRO paciente (no se cambia nada)
      "formato_invalido"
    """
    numero = normalizar_peticion(id_peticion)
    if not numero:
        return "formato_invalido"
    existente = (await db.execute(select(Peticion).where(Peticion.id_peticion == numero))).scalar_one_or_none()
    if existente:
        return "ya_vinculada" if existente.paciente_id == paciente.id else "conflicto"
    db.add(Peticion(id_peticion=numero, paciente_id=paciente.id, fuente=fuente))
    await db.flush()
    return "vinculada"
