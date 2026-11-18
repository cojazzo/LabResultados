import { useEffect, useState } from 'react'
import { Calendar, CheckCircle2, Circle, Download, Droplets, Save } from 'lucide-react'
import {
  descargarEgoPdf,
  getEgo,
  getEgoCampos,
  getEgoPendientes,
  getQuimicosActivos,
  guardarEgo,
} from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useNotification } from '../context/NotificationContext.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'

// Captura del Examen General de Orina: cualquier usuario registra examen físico y microscópico
// (y el químico mientras la tira no lo cargue) de las personas con tira del día. Al guardar, el examen
// toma folio y su PDF queda disponible. El químico que realizó el examen (autor del formato que se transcribe) es obligatorio y firma el reporte.

const formatoFecha = (iso) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('es-MX', { day: 'numeric', month: 'long', year: 'numeric' }) : ''

export default function EgoPage() {
  const { user } = useAuth()
  const notify = useNotification()
  const puedeCapturar = !!user
  const [catalogo, setCatalogo] = useState({ secciones: [], campos: [] })
  const [quimicos, setQuimicos] = useState([])
  const [fecha, setFecha] = useState('')
  const [pendientes, setPendientes] = useState([])
  const [cargandoLista, setCargandoLista] = useState(true)

  const [seleccion, setSeleccion] = useState(null) // paciente_id
  const [examen, setExamen] = useState(null)
  const [cargandoExamen, setCargandoExamen] = useState(false)
  const [guardando, setGuardando] = useState(false)

  const cargarPendientes = async (f) => {
    setCargandoLista(true)
    try {
      const res = await getEgoPendientes(f)
      setPendientes(res.data.items)
      if (!f && res.data.fecha) setFecha(res.data.fecha)
    } catch (err) {
      console.error(err)
      notify.error('No se pudo cargar la lista de personas.')
    } finally {
      setCargandoLista(false)
    }
  }

  useEffect(() => {
    getEgoCampos().then((r) => setCatalogo(r.data)).catch(console.error)
    getQuimicosActivos().then((r) => setQuimicos(r.data)).catch(console.error)
    cargarPendientes()
  }, [])

  const cambiarFecha = (f) => {
    setFecha(f)
    setSeleccion(null)
    setExamen(null)
    if (f) cargarPendientes(f)
  }

  const abrir = async (pacienteId) => {
    setSeleccion(pacienteId)
    setCargandoExamen(true)
    try {
      const res = await getEgo(pacienteId, fecha)
      const datos = res.data
      // Si solo hay un químico activo, es quien escribió el formato: se preselecciona
      if (!datos.quimico_id && quimicos.length === 1) datos.quimico_id = quimicos[0].id
      setExamen(datos)
    } catch (err) {
      console.error(err)
      notify.error('No se pudo abrir el examen.')
    } finally {
      setCargandoExamen(false)
    }
  }

  const cambiar = (clave, valor) => setExamen((e) => ({ ...e, [clave]: valor }))

  const guardar = async (e) => {
    e.preventDefault()
    if (!examen.quimico_id) {
      notify.warning('Selecciona el químico que realizó el examen.')
      return
    }
    setGuardando(true)
    try {
      const payload = { ...examen, quimico_id: Number(examen.quimico_id) }
      const res = await guardarEgo(payload)
      setExamen(res.data)
      notify.success('Examen guardado. Ya puedes descargar el reporte.')
      cargarPendientes(fecha)
    } catch (err) {
      console.error(err)
      notify.error(err.response?.data?.detail || 'No se pudo guardar el examen.')
    } finally {
      setGuardando(false)
    }
  }

  const descargar = async () => {
    try {
      const res = await descargarEgoPdf(examen.id)
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${examen.folio}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error(err)
      notify.error('No se pudo descargar el PDF.')
    }
  }

  const capturados = pendientes.filter((p) => p.capturado).length

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4 p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
        <div>
          <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Droplets className="w-5 h-5 text-teal-600" /> Examen General de Orina
          </h2>
          <p className="text-xs text-slate-400">
            Se reporta EGO a las personas cuyo examen se guarda: al guardar queda disponible el PDF.
          </p>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Fecha de toma
          </label>
          <div className="relative">
            <Calendar className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="date"
              value={fecha}
              onChange={(e) => cambiarFecha(e.target.value)}
              className="pl-9 pr-4 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lista de personas */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex flex-col max-h-[75vh]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Personas con tira</h3>
            <span className="text-xs text-slate-400">
              {capturados}/{pendientes.length} capturados
            </span>
          </div>
          {cargandoLista ? (
            <LoadingSkeleton count={3} />
          ) : pendientes.length === 0 ? (
            <p className="text-sm text-slate-400 py-6 text-center">
              {fecha ? `No hay tiras del ${formatoFecha(fecha)}.` : 'Aún no hay tiras cargadas.'}
            </p>
          ) : (
            <ul className="overflow-y-auto divide-y divide-slate-100 -mx-2">
              {pendientes.map((p) => (
                <li key={p.paciente_id}>
                  <button
                    type="button"
                    onClick={() => abrir(p.paciente_id)}
                    className={`w-full flex items-center gap-3 px-2 py-2.5 text-left rounded-lg transition ${
                      seleccion === p.paciente_id ? 'bg-teal-50' : 'hover:bg-slate-50'
                    }`}
                  >
                    {p.capturado ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" title="Capturado" />
                    ) : (
                      <Circle className="w-4 h-4 text-slate-300 shrink-0" />
                    )}
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-slate-700 truncate">{p.paciente}</span>
                      <span className="block text-[11px] text-slate-400 truncate">{p.identificacion}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Formulario */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          {!seleccion ? (
            <p className="text-sm text-slate-400 py-16 text-center">Selecciona una persona para capturar su examen.</p>
          ) : cargandoExamen || !examen ? (
            <LoadingSkeleton count={4} />
          ) : (
            <form onSubmit={guardar} className="space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-slate-800">{examen.paciente}</h3>
                  <p className="text-xs text-slate-400">
                    {examen.identificacion} · Toma del {formatoFecha(examen.fecha_toma)}
                    {examen.folio && <> · Folio {examen.folio}</>}
                  </p>
                </div>
                <div className="min-w-[220px]">
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Químico que realizó el examen *
                  </label>
                  <select
                    value={examen.quimico_id || ''}
                    onChange={(e) => cambiar('quimico_id', e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm text-slate-700 focus:outline-none focus:border-teal-500"
                  >
                    <option value="">Selecciona químico…</option>
                    {quimicos.map((q) => (
                      <option key={q.id} value={q.id}>{q.nombre_completo}</option>
                    ))}
                  </select>
                </div>
              </div>

              {catalogo.secciones.map((sec) => (
                <section key={sec.clave}>
                  <h4 className="text-xs font-bold text-teal-700 uppercase tracking-wider mb-2">
                    {sec.nombre}
                    {sec.clave === 'quimico' && examen.quimico_fuente === 'tira_uc1000' && (
                      <span className="ml-2 font-normal normal-case text-slate-400">(cargado de la tira)</span>
                    )}
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-[11px] text-slate-400 uppercase tracking-wider">
                          <th className="pb-1 font-semibold w-[38%]">Estudio</th>
                          <th className="pb-1 font-semibold">Resultado</th>
                          <th className="pb-1 font-semibold w-[12%]">Unidades</th>
                          <th className="pb-1 font-semibold w-[20%]">Referencia</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {catalogo.campos
                          .filter((c) => c.seccion === sec.clave)
                          .map((c) => (
                            <tr key={c.clave}>
                              <td className="py-1.5 pr-3 text-slate-700">{c.estudio}</td>
                              <td className="py-1.5 pr-3">
                                <input
                                  aria-label={c.estudio}
                                  value={examen[c.clave] ?? ''}
                                  onChange={(e) => cambiar(c.clave, e.target.value)}
                                  list={c.sugerencias.length ? `sug-${c.clave}` : undefined}
                                  disabled={!puedeCapturar}
                                  maxLength={c.clave === 'sedimento' ? 1000 : 100}
                                  className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-teal-500 disabled:bg-slate-50"
                                />
                                {c.sugerencias.length > 0 && (
                                  <datalist id={`sug-${c.clave}`}>
                                    {c.sugerencias.map((s) => <option key={s} value={s} />)}
                                  </datalist>
                                )}
                              </td>
                              <td className="py-1.5 pr-3 text-xs text-slate-500">{c.unidades || '—'}</td>
                              <td className="py-1.5 text-xs text-slate-500">{c.referencia || '—'}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}

              <div>
                <label className="block text-xs font-bold text-teal-700 uppercase tracking-wider mb-2">
                  Observaciones
                </label>
                <textarea
                  rows={3}
                  value={examen.observaciones ?? ''}
                  onChange={(e) => cambiar('observaciones', e.target.value)}
                  disabled={!puedeCapturar}
                  maxLength={2000}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm text-slate-800 focus:outline-none focus:border-teal-500 disabled:bg-slate-50"
                />
              </div>

              <div className="flex flex-wrap justify-end gap-3">
                {examen.folio && (
                  <button
                    type="button"
                    onClick={descargar}
                    className="px-4 py-2 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 flex items-center gap-2 text-sm font-medium"
                  >
                    <Download className="w-4 h-4" /> Descargar PDF
                  </button>
                )}
                {puedeCapturar && (
                  <button
                    type="submit"
                    disabled={guardando}
                    className="px-6 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-60 text-white font-medium rounded-xl shadow-sm flex items-center gap-2 text-sm"
                  >
                    <Save className="w-4 h-4" />{' '}
                    {guardando ? 'Guardando…' : 'Guardar'}
                  </button>
                )}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
