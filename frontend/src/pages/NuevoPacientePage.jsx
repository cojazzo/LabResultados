import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowLeft, UserPlus, AlertTriangle, Loader2 } from 'lucide-react'
import api from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'

// Opciones del cuestionario: son las mismas del Google Forms (los valores se guardan tal cual para que las
// estadísticas sigan agrupando igual). "Otro" abre un campo de texto.
const DERECHOHABIENCIA = ['IMSS', 'ISSSTE', 'INSABI', 'Particular', 'Ninguno']
const TIPOS_AGUA = [
  { value: 'agua de marca reconocida (ciel, bonafont, epura, etc.).', label: 'Agua de marca reconocida (Ciel, Bonafont, Epura, etc.)' },
  { value: 'agua rellanada', label: 'Agua rellenada (garrafón)' },
  { value: 'agua de la llave', label: 'Agua de la llave' },
]
const PADECIMIENTOS = [
  'Ningun padecimiento',
  'Hipertensión(presión alta)',
  'Algun familiar cuenta con enfermedad renal',
  'Obesidad',
  'Infecciones urinarias de repeticion',
  'Diabetes',
  'Enfermedad del corazon',
]
const NINGUNO = 'Ningun padecimiento'
const CURP_RE = /^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$/

const VACIO = {
  nombre: '', apellido_paterno: '', apellido_materno: '', sexo: '', fecha_nacimiento: '', curp: '',
  telefono: '', email: '',
  domicilio: '', codigo_postal: '', estado_residencia: 'Aguascalientes', municipio_residencia: '',
  peso: '', estatura: '', derechohabiencia: '', derechohabiencia_otro: '',
  toma_suplemento: 'No', suplemento_detalle: '', tipo_agua: '', cocina_agua_llave: '',
  padecimientos: [], padecimiento_otro: '',
  consent_email: false, consent_whatsapp: false, consent_entrega: false,
  id_peticion: '', campana_id: '',
}

const inputCls = 'w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500'

function Campo({ label, error, ayuda, children, className = '' }) {
  return (
    <div className={className}>
      <label className="block text-xs font-medium text-slate-500 mb-1">{label}</label>
      {children}
      {ayuda && !error && <p className="text-xs text-slate-400 mt-1">{ayuda}</p>}
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  )
}

function Seccion({ titulo, children }) {
  return (
    <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
      <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">{titulo}</h2>
      {children}
    </section>
  )
}

function edadDe(fecha) {
  if (!fecha) return null
  const n = new Date(fecha)
  if (Number.isNaN(n.getTime())) return null
  const hoy = new Date()
  let edad = hoy.getFullYear() - n.getFullYear()
  if (hoy.getMonth() < n.getMonth() || (hoy.getMonth() === n.getMonth() && hoy.getDate() < n.getDate())) edad--
  return edad
}

export default function NuevoPacientePage() {
  const navigate = useNavigate()
  const notify = useNotification()
  const [f, setF] = useState(VACIO)
  const [errores, setErrores] = useState({})
  const [campanas, setCampanas] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [errorServidor, setErrorServidor] = useState('')
  const [conflicto, setConflicto] = useState(null)

  useEffect(() => {
    api.get('/campanas').then((r) => setCampanas(r.data || [])).catch(() => setCampanas([]))
  }, [])

  const set = (campo, valor) => setF((prev) => ({ ...prev, [campo]: valor }))
  const onChange = (e) => set(e.target.name, e.target.type === 'checkbox' ? e.target.checked : e.target.value)
  const edad = useMemo(() => edadDe(f.fecha_nacimiento), [f.fecha_nacimiento])

  const togglePadecimiento = (op) => {
    setF((prev) => {
      const actual = new Set(prev.padecimientos)
      if (actual.has(op)) actual.delete(op)
      else if (op === NINGUNO) { actual.clear(); actual.add(op) }       // "ninguno" excluye a los demás
      else { actual.delete(NINGUNO); actual.add(op) }
      return { ...prev, padecimientos: [...actual] }
    })
  }

  const validar = () => {
    const e = {}
    if (!f.nombre.trim()) e.nombre = 'Obligatorio'
    if (!f.apellido_paterno.trim()) e.apellido_paterno = 'Obligatorio'
    if (!f.sexo) e.sexo = 'Obligatorio'
    if (!f.fecha_nacimiento) e.fecha_nacimiento = 'Obligatoria'
    else if (new Date(f.fecha_nacimiento) > new Date()) e.fecha_nacimiento = 'No puede ser futura'
    const curp = f.curp.trim().toUpperCase()
    if (curp && !CURP_RE.test(curp)) e.curp = 'No tiene el formato de una CURP (18 caracteres)'
    if (f.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(f.email.trim())) e.email = 'Correo no válido'
    const tel = f.telefono.replace(/\D/g, '')
    if (f.telefono.trim() && (tel.length < 8 || tel.length > 15)) e.telefono = 'Entre 8 y 15 dígitos'
    if (f.peso && !(Number(f.peso) >= 1 && Number(f.peso) <= 400)) e.peso = '1 a 400 kg'
    if (f.estatura) {
      const cm = Number(f.estatura) < 3 ? Number(f.estatura) * 100 : Number(f.estatura)
      if (!(cm >= 30 && cm <= 250)) e.estatura = '30 a 250 cm'
    }
    if (f.id_peticion.trim() && !/^(\d{2})?\d{8}$/.test(f.id_peticion.replace(/\s/g, ''))) e.id_peticion = '8 dígitos'
    setErrores(e)
    return Object.keys(e).length === 0
  }

  const armarPayload = (confirmar) => {
    const padecimientos = [...f.padecimientos]
    if (f.padecimiento_otro.trim()) padecimientos.push(f.padecimiento_otro.trim())
    return {
      nombre: f.nombre.trim(),
      apellido_paterno: f.apellido_paterno.trim(),
      apellido_materno: f.apellido_materno.trim() || null,
      sexo: f.sexo,
      fecha_nacimiento: f.fecha_nacimiento,
      curp: f.curp.trim().toUpperCase() || null,
      telefono: f.telefono.trim() || null,
      email: f.email.trim() || null,
      domicilio: f.domicilio.trim() || null,
      codigo_postal: f.codigo_postal.trim() || null,
      estado_residencia: f.estado_residencia.trim() || null,
      municipio_residencia: f.municipio_residencia.trim() || null,
      peso: f.peso ? Number(f.peso) : null,
      estatura: f.estatura ? Number(f.estatura) : null,
      derechohabiencia: (f.derechohabiencia === 'Otro' ? f.derechohabiencia_otro.trim() : f.derechohabiencia) || null,
      suplemento: f.toma_suplemento === 'Sí' ? (f.suplemento_detalle.trim() || 'Sí') : 'No',
      tipo_agua: f.tipo_agua || null,
      cocina_agua_llave: f.cocina_agua_llave || null,
      padecimientos: padecimientos.length ? padecimientos : null,
      consentimientos: { email: f.consent_email, whatsapp: f.consent_whatsapp, entrega_resultados: f.consent_entrega },
      id_peticion: f.id_peticion.trim() || null,
      campana_id: f.campana_id ? Number(f.campana_id) : null,
      confirmar_actualizacion: confirmar,
    }
  }

  const enviar = async (confirmar = false) => {
    setErrorServidor('')
    if (!validar()) {
      setErrorServidor('Revisa los campos marcados.')
      return
    }
    setEnviando(true)
    try {
      const res = await api.post('/pacientes', armarPayload(confirmar))
      const d = res.data
      const accion = { creado: 'creado', actualizado: 'actualizado', adoptado: 'actualizado (adoptó la CURP)', fusionado: 'actualizado y unido a un perfil previo' }[d.accion] || d.accion
      notify.success(`Paciente ${accion}.`)
      if (d.peticion === 'conflicto') notify.error('La petición ya estaba vinculada a otra persona; no se cambió.')
      if (d.revisar?.length) notify.info(`Hay ${d.revisar.length} perfil(es) con nombre parecido para revisar.`)
      navigate(`/perfiles/${d.paciente_id}`)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 409 && detail?.codigo === 'paciente_existente') {
        setConflicto(detail)
      } else {
        setErrorServidor(typeof detail === 'string' ? detail : 'No se pudo guardar. Intenta de nuevo.')
      }
    } finally {
      setEnviando(false)
    }
  }

  const textoConflicto = (c) => ({
    actualizado: 'Ya existe una persona con esa CURP. Se actualizarán sus datos con lo capturado aquí.',
    adoptado: 'Ya hay un perfil de laboratorio sin CURP con exactamente este nombre. Se le asignará esta CURP y conservará sus resultados.',
    fusionado: 'Ya existe esa CURP y además un perfil de laboratorio con este nombre: se unirán en uno solo.',
  }[c.accion] || 'Esta persona ya existe.')

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3">
        <Link to="/perfiles" className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"><ArrowLeft className="w-5 h-5" /></Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Nuevo paciente</h1>
          <p className="text-slate-500 text-sm">Datos personales y cuestionario. Si la persona ya existe no se crea un duplicado.</p>
        </div>
      </div>

      {conflicto && (
        <div className="p-4 rounded-2xl border border-amber-300 bg-amber-50 text-amber-900 space-y-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div className="text-sm space-y-1">
              <p className="font-semibold">{conflicto.nombre} <span className="font-mono text-xs font-normal">({conflicto.identificacion})</span></p>
              <p>{textoConflicto(conflicto)}</p>
              {conflicto.revisar?.length > 0 && (
                <p className="text-xs">Además hay {conflicto.revisar.length} perfil(es) con nombre parecido que conviene revisar.</p>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/perfiles/${conflicto.paciente_id}`} className="px-3 py-1.5 text-sm rounded-lg border border-amber-300 bg-white hover:bg-amber-100">Ver perfil existente</Link>
            <button type="button" disabled={enviando} onClick={() => { setConflicto(null); enviar(true) }}
              className="px-3 py-1.5 text-sm rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-60">Actualizar con estos datos</button>
            <button type="button" onClick={() => setConflicto(null)} className="px-3 py-1.5 text-sm rounded-lg text-amber-800 hover:bg-amber-100">Cancelar</button>
          </div>
        </div>
      )}

      <Seccion titulo="Datos personales">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Campo label="Nombre(s) *" error={errores.nombre}><input name="nombre" value={f.nombre} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Apellido paterno *" error={errores.apellido_paterno}><input name="apellido_paterno" value={f.apellido_paterno} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Apellido materno"><input name="apellido_materno" value={f.apellido_materno} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Sexo *" error={errores.sexo}>
            <select name="sexo" value={f.sexo} onChange={onChange} className={inputCls}>
              <option value="">Selecciona…</option>
              <option value="F">Femenino</option>
              <option value="M">Masculino</option>
            </select>
          </Campo>
          <Campo label="Fecha de nacimiento *" error={errores.fecha_nacimiento} ayuda={edad !== null ? `${edad} años` : undefined}>
            <input type="date" name="fecha_nacimiento" value={f.fecha_nacimiento} onChange={onChange} className={inputCls} />
          </Campo>
          <Campo label="CURP" error={errores.curp} ayuda="Si no la tiene, déjala vacía.">
            <input name="curp" value={f.curp} maxLength={18} onChange={(e) => set('curp', e.target.value.toUpperCase().replace(/\s/g, ''))}
              className={`${inputCls} font-mono`} />
          </Campo>
          <Campo label="Teléfono" error={errores.telefono}><input name="telefono" value={f.telefono} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Correo electrónico" error={errores.email} className="sm:col-span-2"><input type="email" name="email" value={f.email} onChange={onChange} className={inputCls} /></Campo>
        </div>
      </Seccion>

      <Seccion titulo="Domicilio">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Campo label="Calle, número y colonia" className="sm:col-span-3"><input name="domicilio" value={f.domicilio} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Código postal"><input name="codigo_postal" value={f.codigo_postal} maxLength={5} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Estado de residencia"><input name="estado_residencia" value={f.estado_residencia} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Municipio"><input name="municipio_residencia" value={f.municipio_residencia} onChange={onChange} className={inputCls} /></Campo>
        </div>
      </Seccion>

      <Seccion titulo="Cuestionario">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Campo label="Peso (kg)" error={errores.peso}><input type="number" step="0.1" name="peso" value={f.peso} onChange={onChange} className={inputCls} /></Campo>
          <Campo label="Estatura (cm)" error={errores.estatura} ayuda="En centímetros, ej. 140.">
            <input type="number" step="0.1" name="estatura" value={f.estatura} onChange={onChange} className={inputCls} />
          </Campo>
          <Campo label="Derechohabiencia">
            <select name="derechohabiencia" value={f.derechohabiencia} onChange={onChange} className={inputCls}>
              <option value="">Selecciona…</option>
              {DERECHOHABIENCIA.map((o) => <option key={o} value={o}>{o}</option>)}
              <option value="Otro">Otro…</option>
            </select>
            {f.derechohabiencia === 'Otro' && (
              <input name="derechohabiencia_otro" value={f.derechohabiencia_otro} onChange={onChange} placeholder="¿Cuál?" className={`${inputCls} mt-2`} />
            )}
          </Campo>
          <Campo label="¿Toma algún suplemento?">
            <select name="toma_suplemento" value={f.toma_suplemento} onChange={onChange} className={inputCls}>
              <option value="No">No</option>
              <option value="Sí">Sí</option>
            </select>
            {f.toma_suplemento === 'Sí' && (
              <input name="suplemento_detalle" value={f.suplemento_detalle} onChange={onChange} placeholder="¿Cuál?" className={`${inputCls} mt-2`} />
            )}
          </Campo>
          <Campo label="¿Qué tipo de agua toma?" className="sm:col-span-2">
            <select name="tipo_agua" value={f.tipo_agua} onChange={onChange} className={inputCls}>
              <option value="">Selecciona…</option>
              {TIPOS_AGUA.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </Campo>
          <Campo label="¿Cocina con agua de la llave?">
            <select name="cocina_agua_llave" value={f.cocina_agua_llave} onChange={onChange} className={inputCls}>
              <option value="">Selecciona…</option>
              <option value="Sí">Sí</option>
              <option value="No">No</option>
            </select>
          </Campo>
        </div>
        <div>
          <p className="block text-xs font-medium text-slate-500 mb-2">Padecimientos (selecciona uno o varios)</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {PADECIMIENTOS.map((op) => (
              <label key={op} className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={f.padecimientos.includes(op)} onChange={() => togglePadecimiento(op)}
                  className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                {op}
              </label>
            ))}
          </div>
          <input name="padecimiento_otro" value={f.padecimiento_otro} onChange={onChange} placeholder="Otro padecimiento (opcional)" className={`${inputCls} mt-3`} />
        </div>
      </Seccion>

      <Seccion titulo="Consentimientos">
        <div className="space-y-2 text-sm text-slate-700">
          <label className="flex items-center gap-2"><input type="checkbox" name="consent_email" checked={f.consent_email} onChange={onChange} className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" /> Acepta recibir información por correo electrónico</label>
          <label className="flex items-center gap-2"><input type="checkbox" name="consent_whatsapp" checked={f.consent_whatsapp} onChange={onChange} className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" /> Acepta recibir información por WhatsApp</label>
          <label className="flex items-center gap-2"><input type="checkbox" name="consent_entrega" checked={f.consent_entrega} onChange={onChange} className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" /> Autoriza la entrega de sus resultados por estos medios</label>
        </div>
      </Seccion>

      <Seccion titulo="Vinculación (opcional)">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Campo label="ID de petición" error={errores.id_peticion} ayuda="Si solo se hará tira (sin Vitros): 8 dígitos, ej. 99922201. Así sus resultados de la tira se cargan en este perfil.">
            <input name="id_peticion" value={f.id_peticion} onChange={onChange} className={`${inputCls} font-mono`} />
          </Campo>
          <Campo label="Inscribir en campaña">
            <select name="campana_id" value={f.campana_id} onChange={onChange} className={inputCls}>
              <option value="">Ninguna</option>
              {campanas.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </Campo>
        </div>
      </Seccion>

      {errorServidor && <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">{errorServidor}</div>}

      <div className="flex justify-end gap-3 pb-6">
        <Link to="/perfiles" className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100">Cancelar</Link>
        <button type="button" disabled={enviando} onClick={() => enviar(false)}
          className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-emerald-600 text-white font-medium hover:bg-emerald-700 disabled:opacity-60">
          {enviando ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />} Dar de alta
        </button>
      </div>
    </div>
  )
}
