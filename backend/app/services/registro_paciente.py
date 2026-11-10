"""
Aplicación de los datos personales y del cuestionario a un perfil de paciente.

La usan el importador del Google Forms (Excel / n8n) y el alta manual de la aplicación, para que ambos guarden
exactamente lo mismo y con las mismas reglas:
  - perfil nuevo: se crea con los datos no vacíos;
  - perfil existente: solo se actualizan los campos con valor (un dato vacío nunca borra uno existente);
  - alumnos del padrón de tamiz-escolar: nombre, apellidos, nacimiento y sexo los manda tamiz y no se sobrescriben.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Paciente

# Los manda tamiz-escolar para los alumnos del padrón
CAMPOS_DE_IDENTIDAD = ("nombre", "apellido", "apellido_materno", "fecha_nacimiento", "sexo")


def _vacio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


async def aplicar_datos(db: AsyncSession, paciente: Optional[Paciente], identificacion: str, datos: dict,
                        origen: Optional[str] = None) -> Paciente:
    """
    Crea (paciente=None) o actualiza el perfil con `datos` (claves = columnas de Paciente). No confirma la transacción.
    Un booleano False cuenta como valor (p. ej. un consentimiento que se retira); None y texto en blanco no.
    """
    con_valor = {k: (v.strip() if isinstance(v, str) else v) for k, v in datos.items() if not _vacio(v)}
    if paciente is None:
        extra = {"origen": origen} if origen else {}
        paciente = Paciente(identificacion=identificacion, **extra, **con_valor)
        db.add(paciente)
    else:
        for campo, valor in con_valor.items():
            if campo in CAMPOS_DE_IDENTIDAD and paciente.folio_tamiz:
                continue
            setattr(paciente, campo, valor)
    await db.flush()
    return paciente
