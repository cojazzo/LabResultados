"""
Resolución de identidad de pacientes que llegan por formulario (Google Forms).

El formulario trae datos personales y clínicos con la CURP que la persona captura; los resultados del
laboratorio (tira UC-1000 y Vitros) pueden haber llegado antes y haber creado un perfil sin CURP
(SYN-..., NTS-..., número de petición). Aquí se decide a qué perfil pertenece la respuesta:

  1. La CURP ya existe                -> se actualiza ese perfil y, si hay un perfil de laboratorio sin CURP
                                         con exactamente el mismo nombre, se fusiona en él.
  2. La CURP no existe pero hay un    -> ese perfil "adopta" la CURP (conserva sus resultados).
     único perfil de laboratorio sin
     CURP con el mismo nombre
  3. Sin coincidencia                 -> perfil nuevo.

Solo se une automáticamente con nombre completo EXACTO (sin acentos, mayúsculas ni orden) y sin
contradicciones de sexo o fecha de nacimiento. Si hay varios candidatos o el nombre es solo parecido,
no se une nada y se devuelve la lista en `revisar` para que una persona decida.
Los alumnos del padrón de tamiz-escolar (folio_tamiz) nunca se tocan: sus datos los manda tamiz.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Paciente
from app.services.pacientes_merge import fusionar_paciente, pruebas_renales
from app.services.tamiz_sync import _norm_nombre
from app.utils.curp_validator import generate_synthetic_id

CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$")
UMBRAL_PARECIDO = 0.93
DOB_PLAUSIBLE_ANTES_DE = date(2025, 1, 1)   # las fechas de nacimiento "de hoy" son basura de cargas de laboratorio


def curp_valida(valor) -> Optional[str]:
    if not valor:
        return None
    curp = re.sub(r"[^A-Za-z0-9]", "", str(valor)).upper()
    return curp if CURP_RE.match(curp) else None


def _tokens(*partes) -> str:
    return " ".join(sorted(_norm_nombre(*partes).split()))


@dataclass
class ResultadoIdentidad:
    paciente: Optional[Paciente]          # None = hay que crear el perfil
    identificacion: str                   # identificación con la que se crea o que conserva el perfil
    accion: str                           # creado | actualizado | adoptado | fusionado
    fusionados: int = 0
    revisar: list = field(default_factory=list)   # [{id, identificacion, nombre, motivo}]


def _sexos_compatibles(a: Optional[str], b: Optional[str]) -> bool:
    return not a or not b or a.strip().upper()[:1] == b.strip().upper()[:1]


def _dob_compatibles(candidato: Optional[date], formulario: Optional[date]) -> bool:
    if not candidato or not formulario or candidato == formulario:
        return True
    return candidato >= DOB_PLAUSIBLE_ANTES_DE      # una fecha basura no contradice


class ResolvedorIdentidad:
    """Índice (una sola carga por lote de respuestas) de perfiles de laboratorio sin CURP."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._indice: Optional[list[tuple[int, str]]] = None      # (paciente_id, nombre normalizado)
        self._pruebas: Optional[dict] = None

    async def _cargar(self):
        if self._indice is not None:
            return
        res = await self.db.execute(
            select(Paciente).where(Paciente.folio_tamiz.is_(None), Paciente.questionnaire_source_id.is_(None)))
        self._indice = [
            (p.id, _tokens(p.nombre, p.apellido, p.apellido_materno))
            for p in res.scalars().all() if not curp_valida(p.identificacion)
        ]

    async def _candidatos(self, nombre, ap_pat, ap_mat, sexo, nacimiento, excluir_id=None):
        """(exactos, parecidos): perfiles de laboratorio sin CURP con el mismo nombre / un nombre muy parecido."""
        objetivo = _tokens(nombre, ap_pat, ap_mat)
        if len(objetivo.split()) < 2:
            return [], []
        await self._cargar()
        exactos, parecidos = [], []
        for pid, tokens in self._indice:
            if pid == excluir_id:
                continue
            if tokens == objetivo:
                exactos.append(pid)
            elif SequenceMatcher(None, objetivo, tokens).ratio() >= UMBRAL_PARECIDO:
                parecidos.append(pid)
        pacientes = {}
        for pid in exactos + parecidos:
            pacientes[pid] = (await self.db.execute(select(Paciente).where(Paciente.id == pid))).scalar_one()

        def compatible(p):
            return _sexos_compatibles(p.sexo, sexo) and _dob_compatibles(p.fecha_nacimiento, nacimiento)

        return ([pacientes[i] for i in exactos if compatible(pacientes[i])],
                [pacientes[i] for i in parecidos if compatible(pacientes[i])])

    def _quitar_del_indice(self, pid: int):
        if self._indice is not None:
            self._indice = [(i, t) for i, t in self._indice if i != pid]

    @staticmethod
    def _ficha(p: Paciente, motivo: str) -> dict:
        return {"id": p.id, "identificacion": p.identificacion,
                "nombre": f"{p.nombre} {p.apellido} {p.apellido_materno or ''}".strip(), "motivo": motivo}

    async def resolver(self, curp, nombre, ap_pat, ap_mat=None, sexo=None,
                       nacimiento: Optional[date] = None) -> ResultadoIdentidad:
        curp = curp_valida(curp)
        exactos, parecidos = await self._candidatos(nombre, ap_pat, ap_mat, sexo, nacimiento)
        revisar = [self._ficha(p, "nombre parecido, no se unió") for p in parecidos]

        if curp:
            existente = (await self.db.execute(select(Paciente).where(Paciente.identificacion == curp))
                         ).scalar_one_or_none()
            if existente:
                if existente.folio_tamiz:              # alumno del padrón: no se fusiona nada en él
                    return ResultadoIdentidad(existente, curp, "actualizado", revisar=revisar)
                fusionados = 0
                if len(exactos) == 1:
                    cuenta_pruebas = self._pruebas or await pruebas_renales(self.db)
                    self._pruebas = cuenta_pruebas
                    dup = exactos[0]
                    await fusionar_paciente(self.db, dup, existente, cuenta_pruebas)
                    self._quitar_del_indice(dup.id)
                    fusionados = 1
                elif len(exactos) > 1:
                    revisar += [self._ficha(p, "varios perfiles con el mismo nombre, no se unió") for p in exactos]
                return ResultadoIdentidad(existente, curp, "fusionado" if fusionados else "actualizado",
                                          fusionados=fusionados, revisar=revisar)
            if len(exactos) == 1:
                adoptante = exactos[0]
                adoptante.identificacion = curp
                self._quitar_del_indice(adoptante.id)
                return ResultadoIdentidad(adoptante, curp, "adoptado", revisar=revisar)
            if len(exactos) > 1:
                revisar += [self._ficha(p, "varios perfiles con el mismo nombre, no se unió") for p in exactos]
            return ResultadoIdentidad(None, curp, "creado", revisar=revisar)

        # Sin CURP: se reutiliza el perfil de laboratorio con el mismo nombre, o se crea uno SYN
        if len(exactos) == 1:
            return ResultadoIdentidad(exactos[0], exactos[0].identificacion, "actualizado", revisar=revisar)
        if len(exactos) > 1:
            revisar += [self._ficha(p, "varios perfiles con el mismo nombre, no se unió") for p in exactos]
        # misma fórmula que ya usaba la importación del Excel, para reconocer perfiles SYN existentes
        sintetico = generate_synthetic_id(nombre, ap_pat, sexo, None)
        existente = (await self.db.execute(select(Paciente).where(Paciente.identificacion == sintetico))
                     ).scalar_one_or_none()
        return ResultadoIdentidad(existente, sintetico, "actualizado" if existente else "creado", revisar=revisar)
