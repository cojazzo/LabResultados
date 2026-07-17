import { useState, useEffect, useCallback } from 'react'
import {
  getDashboardResumen,
  getDashboardTendencia,
  getDashboardAnormales,
  getDashboardTopPruebas,
  getResultados,
  descargarReporte,
  getDashboardMapaPacientes,
  geocodificarPacientes,
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
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from 'recharts'
import {
  Activity,
  Users,
  AlertTriangle,
  FileText,
  Clock,
  CheckCircle,
  Eye,
  Calendar,
  MapPin,
  RefreshCw,
} from 'lucide-react'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import StatCard from '../components/StatCard.jsx'
import Badge from '../components/Badge.jsx'
import MapaPacientes from '../components/MapaPacientes.jsx'

const COLORS = ['#10b981', '#f59e0b', '#f97316', '#ef4444', '#3b82f6']

export default function DashboardPage() {
  const notify = useNotification()
  const [loading, setLoading] = useState(true)
  const [resumen, setResumen] = useState(null)
  const [tendencia, setTendencia] = useState([])
  const [anormales, setAnormales] = useState([])
  const [topPruebas, setTopPruebas] = useState([])
  const [recientes, setRecientes] = useState([])
  const [mapaPuntos, setMapaPuntos] = useState([])
  const [loadingMapa, setLoadingMapa] = useState(true)
  const [geocodificando, setGeocodificando] = useState(false)
  
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')

  const fetchData = async () => {
    setLoading(true)
    try {
      const filters = {}
      if (fechaDesde) filters.desde = fechaDesde
      if (fechaHasta) filters.hasta = fechaHasta

      const [resResumen, resTendencia, resAnormales, resTop, resRecientes] = await Promise.all([
        getDashboardResumen(filters),
        getDashboardTendencia(filters),
        getDashboardAnormales(),
        getDashboardTopPruebas(5),
        getResultados({ limit: 10 }),
      ])

      setResumen(resResumen.data)
      setTendencia(resTendencia.data)
      setAnormales(resAnormales.data)
      setTopPruebas(resTop.data)
      setRecientes(resRecientes.data)
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar datos del dashboard.')
    } finally {
      setLoading(false)
    }
  }

  const fetchMapa = useCallback(async () => {
    setLoadingMapa(true)
    try {
      const res = await getDashboardMapaPacientes()
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

  const handleDescargar = async (loteId, pacienteId) => {
    // Para simplificar, buscamos si hay reportes generados. Si no, avisamos que debe generarlo desde Resultados.
    notify.info('Buscando reporte para descargar...')
    try {
      // El backend requiere descargar reportes por ID. 
      // Por ende, redirigimos a Resultados para que el usuario maneje reportes.
      notify.warning('Ve a la sección "Resultados" para generar y descargar PDFs.')
    } catch (err) {
      notify.error('No se pudo descargar el reporte.')
    }
  }

  if (loading && !resumen) {
    return <LoadingSkeleton count={4} />
  }

  return (
    <div className="space-y-6">
      {/* ── Filters bar ────────────────────────────────────────── */}
      <form onSubmit={handleApplyFilter} className="flex flex-wrap items-end gap-4 p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Desde
          </label>
          <div className="relative">
            <input
              type="date"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
              className="w-full px-4 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
            />
          </div>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Hasta
          </label>
          <div className="relative">
            <input
              type="date"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
              className="w-full px-4 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
            />
          </div>
        </div>
        <button
          type="submit"
          className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium rounded-xl shadow-sm hover:shadow active:scale-98 transition flex items-center gap-2"
        >
          <Calendar className="w-4 h-4" />
          <span>Filtrar</span>
        </button>
      </form>

      {/* ── KPI Row ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={Activity}
          title="Pruebas Procesadas"
          value={resumen?.total_pruebas || 0}
          color="teal"
        />
        <StatCard
          icon={Users}
          title="Pacientes Registrados"
          value={resumen?.total_pacientes || 0}
          color="blue"
        />
        <StatCard
          icon={AlertTriangle}
          title="Valores Anormales"
          value={`${resumen?.porcentaje_fuera_rango || 0}%`}
          color={resumen?.porcentaje_fuera_rango > 20 ? 'red' : 'orange'}
        />
        <StatCard
          icon={FileText}
          title="Reportes PDF"
          value={resumen?.total_reportes || 0}
          color="emerald"
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
          <MapaPacientes puntos={mapaPuntos} loading={loadingMapa} />
        </div>
      </div>

      {/* ── Charts Grid ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Line Chart: Tendencia */}
        <div className="lg:col-span-2 p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[350px]">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
            Volumen de Pruebas en el Tiempo
          </h3>
          <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tendencia}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="periodo" stroke="#94a3b8" fontSize={10} />
                <YAxis stroke="#94a3b8" fontSize={10} />
                <Tooltip />
                <Line type="monotone" dataKey="cantidad" stroke="#0d9488" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pie Chart: Distribución Anormales */}
        <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[350px]">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
            Distribución de Resultados
          </h3>
          <div className="flex-1 w-full min-h-0 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={anormales}
                  cx="50%"
                  cy="45%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="cantidad"
                  nameKey="interpretacion"
                >
                  {anormales.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend layout="horizontal" verticalAlign="bottom" align="center" wrapperStyle={{ fontSize: '10px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Bottom Section: Top Pruebas & Recientes ───────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top 5 Pruebas */}
        <div className="p-6 bg-white rounded-2xl border border-slate-100 shadow-sm">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
            Pruebas Más Solicitadas
          </h3>
          <div className="space-y-4">
            {topPruebas.map((p, idx) => (
              <div key={p.codigo} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center text-xs font-bold text-teal-600">
                  #{idx + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-700 truncate">{p.nombre}</p>
                  <p className="text-xs text-slate-400">{p.codigo}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-slate-700">{p.cantidad}</p>
                  <p className="text-[10px] text-slate-400 uppercase">Solicitudes</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recientes */}
        <div className="lg:col-span-2 p-6 bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">
            Resultados Recientes
          </h3>
          <div className="flex-1 overflow-x-auto min-h-0">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">
                  <th className="pb-3 font-semibold">Paciente</th>
                  <th className="pb-3 font-semibold">Estudio</th>
                  <th className="pb-3 font-semibold">Resultado</th>
                  <th className="pb-3 font-semibold">Interpretación</th>
                  <th className="pb-3 font-semibold">Fecha Toma</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recientes.map((r) => (
                  <tr key={r.id} className="text-sm text-slate-600 hover:bg-slate-50/50 transition">
                    <td className="py-3 font-medium text-slate-800">
                      {r.paciente.nombre} {r.paciente.apellido} {r.paciente.apellido_materno || ''}
                    </td>
                    <td className="py-3">
                      <div>{r.prueba.nombre}</div>
                      <div className="text-[10px] text-slate-400 uppercase">{r.prueba.codigo}</div>
                    </td>
                    <td className="py-3 font-bold font-mono">
                      {r.valor !== null ? `${r.valor} ${r.prueba.unidad}` : r.valor_texto}
                    </td>
                    <td className="py-3">
                      <Badge variant={r.interpretacion} />
                    </td>
                    <td className="py-3 text-slate-400 text-xs">
                      {new Date(r.fecha_toma).toLocaleDateString('es-MX')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
