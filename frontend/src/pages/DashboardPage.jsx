import { useState, useEffect, useCallback } from 'react'
import {
  getDashboardResumen,
  getDashboardTendencia,
  getDashboardRiesgoKdigo,
  getDashboardTopPruebas,
  getDashboardRecientes,
  getDashboardMapaHexbin,
  geocodificarPacientes,
  getCampanasStatsPorOrigen,
} from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  BarChart,
  Bar,
} from 'recharts'
import {
  Users,
  AlertTriangle,
  FileText,
  ShieldAlert,
  Timer,
  Calendar,
  MapPin,
  RefreshCw,
} from 'lucide-react'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import StatCard from '../components/StatCard.jsx'
import MapaHexbin from '../components/MapaHexbin.jsx'
import KdigoSemaforo from '../components/KdigoSemaforo.jsx'

const COLORS = ['#10b981', '#f59e0b', '#f97316', '#ef4444', '#3b82f6']

const PERIODOS = [
  { valor: 'dia', etiqueta: 'Día' },
  { valor: 'semana', etiqueta: 'Semana' },
  { valor: 'mes', etiqueta: 'Mes' },
]

const aISO = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

const hoyMenos = (dias) => {
  const d = new Date()
  d.setDate(d.getDate() - dias)
  return aISO(d)
}

// "2031-03-10" -> "10 mar"; "2031-03" -> "mar 2031"
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const etiquetaPeriodo = (p) => {
  if (!p) return ''
  const [a, m, d] = p.split('-')
  return d ? `${Number(d)} ${MESES[Number(m) - 1]}` : `${MESES[Number(m) - 1]} ${a}`
}

const COLUMNAS_RECIENTES = [
  { codigo: 'ACR', titulo: 'ACR' },
  { codigo: 'CRE01', titulo: 'Creatinina urinaria' },
  { codigo: 'ALBOR', titulo: 'Albúmina' },
  { codigo: 'CRTS', titulo: 'Creatinina sérica' },
]

const BADGE_RIESGO = {
  green: 'bg-emerald-100 text-emerald-800',
  yellow: 'bg-amber-100 text-amber-800',
  orange: 'bg-orange-100 text-orange-800',
  red: 'bg-red-100 text-red-800',
  gray: 'bg-slate-100 text-slate-500',
}

// Valor de una prueba para la tabla de recientes; las cotas del ACR (">X") se muestran tal cual.
const formatoValor = (v) => {
  if (!v) return '—'
  const num = v.valor_texto?.trim().startsWith('>') ? v.valor_texto : v.valor ?? v.valor_texto
  return num == null ? '—' : `${num}`
}

const porcentaje = (parte, total) => (total ? Math.round((parte / total) * 100) : 0)

function EmptyState({ children }) {
  return (
    <div className="flex-1 flex items-center justify-center text-sm text-slate-400 text-center px-4">
      {children}
    </div>
  )
}

export default function DashboardPage() {
  const notify = useNotification()
  const [loading, setLoading] = useState(true)
  const [resumen, setResumen] = useState(null)
  const [tendencia, setTendencia] = useState([])
  const [kdigo, setKdigo] = useState(null)
  const [periodo, setPeriodo] = useState('semana')
  const [topPruebas, setTopPruebas] = useState([])
  const [recientes, setRecientes] = useState({ fecha: null, total_personas: 0, items: [] })
  const [origenStats, setOrigenStats] = useState([])
  const [mapaPuntos, setMapaPuntos] = useState({ tamizados: [], positivos: [] })
  const [loadingMapa, setLoadingMapa] = useState(true)
  const [geocodificando, setGeocodificando] = useState(false)
  
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')

  const filtrosActuales = (desde = fechaDesde, hasta = fechaHasta) => {
    const filters = {}
    if (desde) filters.desde = desde
    if (hasta) filters.hasta = hasta
    return filters
  }

  const fetchData = async (desde = fechaDesde, hasta = fechaHasta) => {
    setLoading(true)
    try {
      const filters = filtrosActuales(desde, hasta)

      const [resResumen, resTendencia, resKdigo, resTop, resRecientes, resOrigen] = await Promise.all([
        getDashboardResumen(filters),
        getDashboardTendencia({ ...filters, periodo }),
        getDashboardRiesgoKdigo(filters).catch(() => ({ data: null })),
        getDashboardTopPruebas(10, filters),
        getDashboardRecientes(15),
        getCampanasStatsPorOrigen().catch(() => ({ data: [] })),
      ])

      setResumen(resResumen.data)
      setTendencia(resTendencia.data)
      setKdigo(resKdigo.data)
      setTopPruebas(resTop.data)
      setRecientes(resRecientes.data)
      setOrigenStats(resOrigen.data)
    } catch (err) {
      console.error(err)
      notify.error(err.response?.data?.detail || 'Error al cargar datos del dashboard.')
    } finally {
      setLoading(false)
    }
  }

  const fetchTendencia = async (nuevoPeriodo) => {
    try {
      const res = await getDashboardTendencia({ ...filtrosActuales(), periodo: nuevoPeriodo })
      setTendencia(res.data)
    } catch (err) {
      console.error(err)
      notify.error('No se pudo actualizar la tendencia.')
    }
  }

  const handlePeriodo = (nuevo) => {
    setPeriodo(nuevo)
    fetchTendencia(nuevo)
  }

  const aplicarPreset = (dias) => {
    const desde = dias === null ? '' : hoyMenos(dias)
    const hasta = dias === null ? '' : aISO(new Date())
    setFechaDesde(desde)
    setFechaHasta(hasta)
    fetchData(desde, hasta)
  }

  const fetchMapa = useCallback(async () => {
    setLoadingMapa(true)
    try {
      const res = await getDashboardMapaHexbin()
      setMapaPuntos(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingMapa(false)
    }
  }, [])

  const handleGeocodificar = async () => {
    setGeocodificando(true)
    notify.info('Iniciando geocodificación… esto puede tardar según el número de pacientes.')
    try {
      const res = await geocodificarPacientes()
      const { geocodificados, fallidos, sin_geocodificar_restantes } = res.data
      if (geocodificados === 0 && fallidos === 0) {
        notify.info('Todos los pacientes de Aguascalientes ya están geocodificados.')
      } else {
        notify.success(
          `Geocodificación completa: ${geocodificados} ubicados, ${fallidos} sin resultado${
            sin_geocodificar_restantes > 0 ? `, ${sin_geocodificar_restantes} pendientes` : ''
          }.`
        )
      }
      await fetchMapa()
    } catch (err) {
      notify.error('Error al geocodificar pacientes.')
      console.error(err)
    } finally {
      setGeocodificando(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchMapa()
  }, [])

  const handleApplyFilter = (e) => {
    e.preventDefault()
    fetchData()
  }

  if (loading && !resumen) {
    return <LoadingSkeleton count={4} />
  }

  return (
    <div className="space-y-6">
      {/* ── Filters bar ────────────────────────────────────────── */}
      <form onSubmit={handleApplyFilter} className="flex flex-wrap items-end gap-4 p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Desde (fecha de toma)
          </label>
          <input
            type="date"
            value={fechaDesde}
            onChange={(e) => setFechaDesde(e.target.value)}
            className="w-full px-4 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
          />
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Hasta
          </label>
          <input
            type="date"
            value={fechaHasta}
            onChange={(e) => setFechaHasta(e.target.value)}
            className="w-full px-4 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-60 text-white font-medium rounded-xl shadow-sm hover:shadow active:scale-98 transition flex items-center gap-2"
        >
          <Calendar className="w-4 h-4" />
          <span>Filtrar</span>
        </button>
        <div className="flex items-center gap-1.5 text-xs">
          {[
            { etiqueta: '7 días', dias: 7 },
            { etiqueta: '30 días', dias: 30 },
            { etiqueta: '90 días', dias: 90 },
            { etiqueta: 'Todo', dias: null },
          ].map((p) => (
            <button
              key={p.etiqueta}
              type="button"
              onClick={() => aplicarPreset(p.dias)}
              className="px-3 py-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition"
            >
              {p.etiqueta}
            </button>
          ))}
        </div>
      </form>

      {/* ── KPI Row ───────────────────────────────────────────── */}
      {/* Se cuentan personas, no determinaciones: quien se hace ACR, creatinina y albúmina cuenta una vez. */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
        <StatCard
          icon={Users}
          label="Personas evaluadas"
          value={resumen?.total_personas ?? 0}
          hint={`${resumen?.total_determinaciones ?? 0} determinaciones en total`}
          color="from-teal-500 to-teal-700"
        />
        <StatCard
          icon={AlertTriangle}
          label="Con resultados alterados"
          value={resumen?.personas_con_alteraciones ?? 0}
          hint={`${porcentaje(resumen?.personas_con_alteraciones, resumen?.total_personas)}% de las personas evaluadas`}
          color="from-orange-400 to-orange-600"
        />
        <StatCard
          icon={ShieldAlert}
          label="Riesgo renal moderado o mayor"
          value={resumen?.personas_riesgo_renal ?? 0}
          hint={
            resumen?.personas_clasificadas
              ? `${porcentaje(resumen.personas_riesgo_renal, resumen.personas_clasificadas)}% de ${resumen.personas_clasificadas} con TFG o ACR`
              : 'Sin personas con TFG o ACR en el periodo'
          }
          color="from-red-500 to-red-700"
        />
        <StatCard
          icon={FileText}
          label="Reportes generados"
          value={resumen?.total_reportes ?? 0}
          hint={`${resumen?.total_envios_exitosos ?? 0} envíos exitosos · ${resumen?.total_envios_fallidos ?? 0} fallidos`}
          color="from-emerald-500 to-emerald-700"
        />
        <StatCard
          icon={Timer}
          label="Entrega promedio"
          value={resumen?.dias_promedio_entrega != null ? `${resumen.dias_promedio_entrega} d` : '—'}
          hint={
            resumen?.dias_promedio_entrega != null
              ? 'Días entre la toma y el resultado'
              : 'Sin fecha de resultado registrada'
          }
          color="from-blue-500 to-blue-700"
        />
      </div>

      {/* ── Mapa de Pacientes ──────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
        {/* Encabezado de la sección del mapa */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center">
              <MapPin className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-800">Distribución Geográfica de Pacientes</h3>
              <p className="text-xs text-slate-400">Aguascalientes, México &mdash; OpenStreetMap</p>
            </div>
          </div>

          {/* Botón Geocodificar */}
          <button
            onClick={handleGeocodificar}
            disabled={geocodificando}
            title="Consulta las coordenadas de los pacientes de Aguascalientes sin ubicar en el mapa"
            className={`
              flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition
              shadow-sm border
              ${
                geocodificando
                  ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                  : 'bg-teal-600 hover:bg-teal-700 text-white border-teal-700 active:scale-95'
              }
            `}
          >
            <RefreshCw
              className={`w-4 h-4 ${
                geocodificando ? 'animate-spin' : ''
              }`}
            />
            <span>
              {geocodificando ? 'Geocodificando…' : 'Geocodificar pacientes'}
            </span>
          </button>
        </div>

        {/* Contenedor del mapa */}
        <div className="h-[480px] relative">
          <MapaHexbin data={mapaPuntos} loading={loadingMapa} />
        </div>
      </div>

      {/* ── Semáforo KDIGO + origen ────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
            Riesgo Renal KDIGO
          </h3>
          <p className="text-xs text-slate-400 mb-4">Personas por TFG (filas) y albuminuria ACR (columnas)</p>
          <KdigoSemaforo data={kdigo} />
        </div>

        <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[350px] xl:h-auto min-h-[350px]">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
            Pacientes por Origen
          </h3>
          {origenStats.length === 0 ? (
            <EmptyState>Sin pacientes registrados.</EmptyState>
          ) : (
            <div className="flex-1 w-full min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={origenStats} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" stroke="#94a3b8" fontSize={10} allowDecimals={false} />
                  <YAxis dataKey="origen" type="category" stroke="#94a3b8" fontSize={10} width={100} tickFormatter={(val) => val.replace('_', ' ').toUpperCase()} />
                  <Tooltip formatter={(value) => [value, "Pacientes"]} labelFormatter={(label) => label.replace('_', ' ').toUpperCase()} />
                  <Bar dataKey="cantidad" fill="#3b82f6" radius={[0, 4, 4, 0]}>
                    {origenStats.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* ── Tendencia ──────────────────────────────────────────── */}
      <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[350px]">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
              Personas Atendidas en el Tiempo
            </h3>
            <p className="text-xs text-slate-400">Cada persona cuenta una vez por periodo, sin importar cuántas pruebas tenga</p>
          </div>
          <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
            {PERIODOS.map((p) => (
              <button
                key={p.valor}
                type="button"
                onClick={() => handlePeriodo(p.valor)}
                className={`px-3 py-1.5 transition ${
                  periodo === p.valor ? 'bg-teal-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {p.etiqueta}
              </button>
            ))}
          </div>
        </div>
        {tendencia.length === 0 ? (
          <EmptyState>No hay resultados en el periodo seleccionado.</EmptyState>
        ) : (
          <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tendencia}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="periodo" stroke="#94a3b8" fontSize={10} tickFormatter={etiquetaPeriodo} />
                <YAxis stroke="#94a3b8" fontSize={10} allowDecimals={false} />
                <Tooltip
                  labelFormatter={(p) => (periodo === 'semana' ? `Semana del ${etiquetaPeriodo(p)}` : etiquetaPeriodo(p))}
                  formatter={(value) => [value, 'Personas']}
                />
                <Line type="monotone" dataKey="cantidad" stroke="#0d9488" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ── Pruebas realizadas & Resultados recientes ─────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pruebas realizadas */}
        <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-2">
            Pruebas Realizadas
          </h3>
          <p className="text-4xl font-extrabold text-slate-800">{resumen?.total_determinaciones ?? 0}</p>
          <p className="text-xs text-slate-400 mb-4">
            en {resumen?.total_personas ?? 0} personas, en el periodo seleccionado
          </p>
          {topPruebas.length === 0 && (
            <p className="text-sm text-slate-400">No hay pruebas en el periodo seleccionado.</p>
          )}
          <div className="space-y-3">
            {topPruebas.map((p) => (
              <div key={p.codigo} className="flex items-center justify-between gap-3 text-sm">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-700 truncate">{p.nombre}</p>
                  <p className="text-xs text-slate-400">{p.codigo}</p>
                </div>
                <p className="font-bold text-slate-700">{p.cantidad}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Recientes: una fila por persona */}
        <div className="lg:col-span-2 p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
            Resultados Recientes
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            {recientes.fecha
              ? `Tomas del ${new Date(`${recientes.fecha}T00:00:00`).toLocaleDateString('es-MX', { day: 'numeric', month: 'long', year: 'numeric' })} · ${recientes.total_personas} persona(s)${
                  recientes.total_personas > recientes.items.length ? `, se muestran ${recientes.items.length}` : ''
                }`
              : 'Sin resultados registrados'}
          </p>
          {recientes.items.length === 0 ? (
            <EmptyState>No hay resultados recientes.</EmptyState>
          ) : (
            <div className="flex-1 overflow-x-auto min-h-0">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">
                    <th className="pb-3 font-semibold">Paciente</th>
                    {COLUMNAS_RECIENTES.map((c) => (
                      <th key={c.codigo} className="pb-3 pr-3 font-semibold">{c.titulo}</th>
                    ))}
                    <th className="pb-3 font-semibold">Riesgo KDIGO</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recientes.items.map((r) => (
                    <tr key={r.paciente_id} className="text-sm text-slate-600 hover:bg-slate-50/50 transition">
                      <td className="py-3 pr-3 font-medium text-slate-800">{r.paciente}</td>
                      {COLUMNAS_RECIENTES.map((c) => {
                        const v = r.valores[c.codigo]
                        return (
                          <td key={c.codigo} className="py-3 pr-3 font-mono font-bold whitespace-nowrap">
                            {formatoValor(v)}
                            {v && <span className="ml-1 text-[10px] font-normal text-slate-400">{v.unidad}</span>}
                          </td>
                        )
                      })}
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${BADGE_RIESGO[r.color] || BADGE_RIESGO.gray}`}>
                          {r.riesgo}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
