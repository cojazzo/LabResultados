"""
Integración con tamiz-escolar.

- Resuelve folios de tamiz (letra + 8 dígitos, ej. "S26136937") a pacientes de LabResultados.
- Define la fecha de toma de las muestras de campaña escolar (fecha de evaluación en tamiz).
- Sincroniza el padrón de alumnos (upsert idempotente por folio) y los inscribe en la campaña
  "Secundarias <ciclo>".
"""

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campana, CampanaPaciente, Paciente, Resultado

CICLO_DEFAULT = "2026-2027"
FUENTE_REGISTRO = "tamiz_escolar"

# El UC-1000 puede anteponer el modificador de tipo de muestra (2 dígitos), ej. "17S26136937".
_FOLIO_RE = re.compile(r"^(?:\d{2})?([A-Z]\d{8})$")
_FOLIO_ESTRICTO_RE = re.compile(r"^[A-Z]\d{8}$")
_CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$")

RONDAS_DEFAULT = [
    {"numero": 1, "inicio": "2026-10-19", "fin": "2026-12-11",
     "seg_muestra_inicio": "2027-01-07", "seg_muestra_fin": "2027-01-29"},
    {"numero": 2, "inicio": "2027-02-02", "fin": "2027-04-15",
     "seg_muestra_inicio": "2027-05-03", "seg_muestra_fin": "2027-05-28"},
]


# ---------------------------------------------------------------------------
# Folios
# ---------------------------------------------------------------------------

def normalizar_folio(valor) -> Optional[str]:
    """Devuelve el folio de tamiz ("S26136937") o None si el valor no tiene ese formato."""
    if valor is None:
        return None
    v = re.sub(r"\s+", "", str(valor)).upper()
    m = _FOLIO_RE.match(v)
    return m.group(1) if m else None


async def resolver_folio(db: AsyncSession, folio: str) -> Optional[Paciente]:
    res = await db.execute(select(Paciente).where(Paciente.folio_tamiz == folio))
    return res.scalar_one_or_none()


def mensaje_folio_desconocido(folio: str, sugerencia: Optional[str] = None) -> str:
    msg = (
        f"El folio {folio} no existe en LabResultados. Sincroniza el padrón de tamiz-escolar "
        "(o verifica que el folio esté bien capturado) y vuelve a subir el archivo."
    )
    if sugerencia:
        msg += f" {sugerencia}"
    return msg


def _norm_nombre(*partes) -> str:
    texto = " ".join(p for p in partes if p)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn").upper()
    return re.sub(r"[^A-Z ]+", " ", texto).strip()


def _distancia_folios(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b)) if len(a) == len(b) else 99


class SugeridorFolios:
    """
    Sugiere el folio del padrón cuando un folio capturado no existe (típicamente un error de captura
    o una etiqueta de otra escuela). Solo sugiere: nunca asigna resultados por su cuenta.
    Carga el padrón una sola vez, la primera vez que se necesita.
    """

    UMBRAL_NOMBRE = 0.85
    DISTANCIA_MAX = 2

    def __init__(self, db: AsyncSession):
        self.db = db
        self._padron: Optional[list[tuple[str, str]]] = None      # (folio, nombre normalizado)
        self._por_nombre: dict[str, list[str]] = {}

    async def _cargar(self):
        if self._padron is not None:
            return
        res = await self.db.execute(
            select(Paciente.folio_tamiz, Paciente.nombre, Paciente.apellido, Paciente.apellido_materno)
            .where(Paciente.folio_tamiz.is_not(None)))
        self._padron = []
        for folio, nombre, ap, am in res.all():
            n = _norm_nombre(nombre, ap, am)
            self._padron.append((folio, n))
            self._por_nombre.setdefault(n, []).append(folio)

    async def sugerir(self, folio: str, nombre: Optional[str], apellidos: Optional[str]) -> Optional[str]:
        objetivo = _norm_nombre(nombre, apellidos)
        if not objetivo:
            return None
        await self._cargar()
        # 1) folio casi igual (1-2 dígitos) y nombre muy parecido
        candidatos = [
            f for f, n in self._padron
            if _distancia_folios(folio, f) <= self.DISTANCIA_MAX
            and SequenceMatcher(None, objetivo, n).ratio() >= self.UMBRAL_NOMBRE
        ]
        motivo = "folio parecido y mismo nombre"
        # 2) si no, un único alumno con exactamente el mismo nombre (p. ej. cambió de escuela)
        if not candidatos:
            candidatos = self._por_nombre.get(objetivo, [])
            motivo = "mismo nombre"
        if len(candidatos) != 1:
            return None
        return f"¿Quisiste decir {candidatos[0]}? ({motivo} en el padrón; confírmalo y corrige el archivo)"


# ---------------------------------------------------------------------------
# Fecha de toma
# ---------------------------------------------------------------------------

def _a_fecha(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return date.fromisoformat(v.strip()[:10])
        except ValueError:
            return None
    return None


async def _contexto_tamiz(db: AsyncSession, paciente_id: int) -> tuple[Optional[dict], Optional[dict]]:
    """Contexto del paciente en su campaña de secundarias más reciente y metadatos de esa campaña."""
    res = await db.execute(
        select(CampanaPaciente, Campana)
        .join(Campana, Campana.id == CampanaPaciente.campana_id)
        .where(CampanaPaciente.paciente_id == paciente_id, Campana.tipo == "secundaria")
        .order_by(Campana.id.desc())
        .limit(1)
    )
    row = res.first()
    if not row:
        return None, None
    cp, camp = row

    def _load(txt):
        try:
            return json.loads(txt) if txt else None
        except ValueError:
            return None

    return _load(cp.datos_contextuales), _load(camp.metadata_json)


def _seg_muestra_inicio(ctx: Optional[dict], meta: Optional[dict]) -> Optional[date]:
    if not ctx or not meta:
        return None
    for ronda in meta.get("rondas") or []:
        if ronda.get("numero") == ctx.get("ronda"):
            return _a_fecha(ronda.get("seg_muestra_inicio"))
    return None


async def fecha_toma_tamiz(db: AsyncSession, paciente: Paciente, fecha_archivo: Optional[date]) -> Optional[date]:
    """
    Fecha de toma de una muestra de campaña escolar:
      - 1a muestra: la fecha de evaluación registrada en tamiz (así la tira y la confirmación de Vitros
        caen en la misma visita aunque se procesen en días distintos).
      - 2a muestra (archivo con fecha dentro/después de la ventana de segunda muestra): la fecha del archivo.
      - Alumno sin evaluación capturada: la fecha del archivo.
    """
    ctx, meta = await _contexto_tamiz(db, paciente.id)
    evaluacion = _a_fecha(ctx.get("fecha_evaluacion")) if ctx else None
    if not evaluacion:
        return fecha_archivo
    if fecha_archivo is None:
        return evaluacion
    seg_inicio = _seg_muestra_inicio(ctx, meta)
    if seg_inicio and fecha_archivo >= seg_inicio:
        return fecha_archivo
    return evaluacion


# ---------------------------------------------------------------------------
# Campaña
# ---------------------------------------------------------------------------

def slug_campana(ciclo: str) -> str:
    return f"secundarias-{ciclo}"


async def get_or_create_campana(db: AsyncSession, ciclo: str = CICLO_DEFAULT,
                                rondas: Optional[list] = None, total_padron: Optional[int] = None) -> Campana:
    res = await db.execute(select(Campana).where(Campana.slug == slug_campana(ciclo)))
    campana = res.scalar_one_or_none()
    meta = {}
    if campana and campana.metadata_json:
        try:
            meta = json.loads(campana.metadata_json)
        except ValueError:
            meta = {}
    meta["ciclo"] = ciclo
    if rondas:
        meta["rondas"] = rondas
    meta.setdefault("rondas", RONDAS_DEFAULT)
    if total_padron is not None:
        meta["total_padron"] = total_padron

    inicios = [_a_fecha(r.get("inicio")) for r in meta["rondas"] if _a_fecha(r.get("inicio"))]
    fines = [_a_fecha(r.get("seg_muestra_fin") or r.get("fin")) for r in meta["rondas"]
             if _a_fecha(r.get("seg_muestra_fin") or r.get("fin"))]

    if campana is None:
        campana = Campana(
            nombre=f"Secundarias {ciclo}",
            slug=slug_campana(ciclo),
            tipo="secundaria",
            descripcion=f"Tamizaje renal escolar (tercero de secundaria) ciclo {ciclo}, sincronizado desde tamiz-escolar",
            fecha_inicio=min(inicios) if inicios else None,
            fecha_fin=max(fines) if fines else None,
            ubicacion="Aguascalientes",
            estado="activa",
            metadata_json=json.dumps(meta, ensure_ascii=False),
        )
        db.add(campana)
        await db.flush()
    else:
        campana.metadata_json = json.dumps(meta, ensure_ascii=False)
    return campana


# ---------------------------------------------------------------------------
# Sincronización del padrón
# ---------------------------------------------------------------------------

def _limpio(v) -> Optional[str]:
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


def _curp_valida(curp) -> Optional[str]:
    c = re.sub(r"[^A-Za-z0-9]", "", str(curp or "")).upper()
    return c if _CURP_RE.match(c) else None


def _sexo_lab(valor) -> Optional[str]:
    """
    Convierte el sexo de tamiz (convención de la CURP: H = hombre, M = mujer) a la convención de
    LabResultados (M = masculino, F = femenino). Ojo: la "M" de tamiz es MUJER.
    """
    v = (_limpio(valor) or "").upper()
    if v in ("H", "HOMBRE", "MASCULINO"):
        return "M"
    if v in ("M", "MUJER", "F", "FEMENINO"):
        return "F"
    return None


def _asignar(obj, campo: str, valor) -> bool:
    """Asigna solo si hay valor nuevo (tamiz nunca borra datos). Devuelve True si cambió algo."""
    if valor is None or valor == "":
        return False
    if getattr(obj, campo) == valor:
        return False
    setattr(obj, campo, valor)
    return True


async def _realinear_fechas(db: AsyncSession, paciente_id: int, evaluacion: date,
                            seg_inicio: Optional[date]) -> tuple[int, int]:
    """
    Cuando se conoce (o cambia) la fecha de evaluación de un alumno que ya tiene resultados cargados
    con la fecha del archivo, mueve los de la primera muestra a la fecha de evaluación.
    Si ya existe esa misma prueba en la fecha de evaluación no la toca (se cuenta como conflicto).
    """
    res = await db.execute(select(Resultado).where(Resultado.paciente_id == paciente_id))
    todos = res.scalars().all()
    ocupadas = {r.prueba_id for r in todos if r.fecha_toma == evaluacion}
    movidos = conflictos = 0
    for r in todos:
        if r.fecha_toma == evaluacion:
            continue
        if r.fecha_toma < evaluacion - timedelta(days=45):
            continue
        if seg_inicio and r.fecha_toma >= seg_inicio:
            continue
        if r.prueba_id in ocupadas:
            conflictos += 1
            continue
        r.fecha_toma = evaluacion
        ocupadas.add(r.prueba_id)
        movidos += 1
    return movidos, conflictos


async def sincronizar_alumnos(db: AsyncSession, alumnos: list[dict], ciclo: str = CICLO_DEFAULT,
                              rondas: Optional[list] = None, total_padron: Optional[int] = None) -> dict:
    """
    Upsert idempotente de alumnos de tamiz-escolar. La llave estable es el folio.
    No hace commit (lo hace quien llama).
    """
    campana = await get_or_create_campana(db, ciclo, rondas, total_padron)
    meta = json.loads(campana.metadata_json)

    resumen = {"recibidos": len(alumnos), "creados": 0, "actualizados": 0, "sin_cambios": 0,
               "curp_asignada": 0, "curp_corregida": 0, "fechas_realineadas": 0,
               "fechas_en_conflicto": 0, "inscritos_nuevos": 0, "conflictos": []}

    limpios = []
    for a in alumnos:
        folio = re.sub(r"\s+", "", str(a.get("folio") or "")).upper()
        if not _FOLIO_ESTRICTO_RE.match(folio):
            resumen["conflictos"].append({"folio": a.get("folio"), "motivo": "folio con formato inválido"})
            continue
        nombres = _limpio(a.get("nombres"))
        ap1 = _limpio(a.get("primer_apellido"))
        ap2 = _limpio(a.get("segundo_apellido"))
        if not ap1 and ap2:           # la base exige apellido: usar el único que haya
            ap1, ap2 = ap2, None
        if not nombres or not ap1:
            resumen["conflictos"].append({"folio": folio, "motivo": "alumno sin nombre o sin apellido"})
            continue
        limpios.append({**a, "folio": folio, "nombres": nombres, "ap1": ap1, "ap2": ap2,
                        "curp": _curp_valida(a.get("curp"))})

    if not limpios:
        return resumen

    folios = [a["folio"] for a in limpios]
    idents = {a["curp"] for a in limpios if a["curp"]} | {f"TAMIZ-{f}" for f in folios}
    por_folio = {p.folio_tamiz: p for p in (await db.execute(
        select(Paciente).where(Paciente.folio_tamiz.in_(folios)))).scalars()}
    por_ident = {p.identificacion.upper(): p for p in (await db.execute(
        select(Paciente).where(Paciente.identificacion.in_(idents)))).scalars()}

    nuevos, tocados = [], []     # (paciente, alumno, era_nuevo)
    vistos_ident: set[str] = set()

    for a in limpios:
        folio, curp = a["folio"], a["curp"]
        p = por_folio.get(folio)
        if p is None and curp:
            p = por_ident.get(curp)
        if p is None:
            p = por_ident.get(f"TAMIZ-{folio}")
        if p is not None and p.folio_tamiz and p.folio_tamiz != folio:
            resumen["conflictos"].append({"folio": folio, "motivo": f"la CURP ya pertenece al folio {p.folio_tamiz}"})
            continue

        cambios = False
        if p is None:
            ident = curp or f"TAMIZ-{folio}"
            if ident in por_ident or ident in vistos_ident:
                resumen["conflictos"].append({"folio": folio, "motivo": f"identificación {ident} duplicada"})
                continue
            vistos_ident.add(ident)
            p = Paciente(identificacion=ident, nombre=a["nombres"], apellido=a["ap1"],
                         apellido_materno=a["ap2"], origen="secundaria", folio_tamiz=folio)
            db.add(p)
            por_folio[folio] = p
            por_ident[ident] = p
            nuevo = True
            cambios = True
        else:
            nuevo = False
            if p.folio_tamiz != folio:
                p.folio_tamiz = folio
                cambios = True
            por_folio[folio] = p
            if curp and p.identificacion.upper() != curp:
                if curp in por_ident and por_ident[curp] is not p:
                    resumen["conflictos"].append({"folio": folio, "motivo": f"CURP {curp} ya asignada a otro paciente"})
                else:
                    viejo = p.identificacion
                    por_ident.pop(viejo.upper(), None)
                    p.identificacion = curp
                    por_ident[curp] = p
                    resumen["curp_asignada" if viejo.startswith(("TAMIZ-", "SYN-")) else "curp_corregida"] += 1
                    cambios = True
            cambios |= _asignar(p, "nombre", a["nombres"])
            cambios |= _asignar(p, "apellido", a["ap1"])
            cambios |= _asignar(p, "apellido_materno", a["ap2"])

        fnac = _a_fecha(a.get("fecha_nacimiento"))
        sexo = _sexo_lab(a.get("sexo"))
        if sexo and curp and {"M": "H", "F": "M"}[sexo] != curp[10]:
            resumen["conflictos"].append({"folio": folio, "motivo": "el sexo no coincide con el de la CURP (se guardó el de tamiz)"})
        cambios |= _asignar(p, "fecha_nacimiento", fnac)
        cambios |= _asignar(p, "sexo", sexo)
        cambios |= _asignar(p, "telefono", _limpio(a.get("telefono")))
        if a.get("peso_kg") is not None:
            cambios |= _asignar(p, "peso", Decimal(str(a["peso_kg"])))
        if a.get("talla_cm") is not None:
            cambios |= _asignar(p, "estatura", Decimal(str(a["talla_cm"])))
        if p.origen in (None, "servicio_externo"):
            p.origen = "secundaria"
            cambios = True

        if nuevo:
            resumen["creados"] += 1
            nuevos.append((p, a))
        elif cambios:
            resumen["actualizados"] += 1
        else:
            resumen["sin_cambios"] += 1
        tocados.append((p, a, nuevo))

    await db.flush()   # asigna ids a los pacientes nuevos

    ids = [p.id for p, _, _ in tocados]
    existentes = {}
    if ids:
        existentes = {cp.paciente_id: cp for cp in (await db.execute(
            select(CampanaPaciente).where(CampanaPaciente.campana_id == campana.id,
                                          CampanaPaciente.paciente_id.in_(ids)))).scalars()}

    for p, a, nuevo in tocados:
        ctx_nuevo = {
            "folio": a["folio"], "cct": _limpio(a.get("cct")), "escuela": _limpio(a.get("escuela")),
            "subnivel": _limpio(a.get("subnivel")), "municipio": _limpio(a.get("municipio")),
            "localidad": _limpio(a.get("localidad")), "turno": _limpio(a.get("turno")),
            "grado": a.get("grado"), "grupo": _limpio(a.get("grupo")),
            "zona_escolar": _limpio(a.get("zona_escolar")), "provisional": bool(a.get("provisional")),
            "ronda": a.get("ronda"),
            "fecha_evaluacion": (_a_fecha(a.get("fecha_evaluacion")).isoformat()
                                 if _a_fecha(a.get("fecha_evaluacion")) else None),
        }
        cp = existentes.get(p.id)
        if cp is None:
            db.add(CampanaPaciente(campana_id=campana.id, paciente_id=p.id, fuente_registro=FUENTE_REGISTRO,
                                   datos_contextuales=json.dumps(ctx_nuevo, ensure_ascii=False)))
            resumen["inscritos_nuevos"] += 1
            previo = {}
        else:
            try:
                previo = json.loads(cp.datos_contextuales) if cp.datos_contextuales else {}
            except ValueError:
                previo = {}
            if previo != ctx_nuevo:
                cp.datos_contextuales = json.dumps(ctx_nuevo, ensure_ascii=False)

        ev = _a_fecha(ctx_nuevo["fecha_evaluacion"])
        if ev and not nuevo and previo.get("fecha_evaluacion") != ctx_nuevo["fecha_evaluacion"]:
            seg = None
            for r in meta.get("rondas") or []:
                if r.get("numero") == ctx_nuevo["ronda"]:
                    seg = _a_fecha(r.get("seg_muestra_inicio"))
            movidos, conflictos = await _realinear_fechas(db, p.id, ev, seg)
            resumen["fechas_realineadas"] += movidos
            resumen["fechas_en_conflicto"] += conflictos

    await db.flush()
    resumen["campana_id"] = campana.id
    resumen["conflictos"] = resumen["conflictos"][:50]
    return resumen
