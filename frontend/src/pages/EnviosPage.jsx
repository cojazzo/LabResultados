import { useState, useEffect } from 'react'
import { getEnvios, reintentarEnvio } from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'
import { Mail, MessageCircle, Send, AlertTriangle, CheckCircle, Clock, RotateCcw, FileText } from 'lucide-react'
import Badge from '../components/Badge.jsx'
import Pagination from '../components/Pagination.jsx'

export default function EnviosPage() {
  const notify = useNotification()
  const [envios, setEnvios] = useState([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  
  // Filtros
  const [filtroCanal, setFiltroCanal] = useState('todos')
  const [filtroEstado, setFiltroEstado] = useState('todos')
  
  // Estadísticas rápidas
  const [stats, setStats] = useState({ enviados: 0, pendientes: 0, fallidos: 0 })

  const fetchEnvios = async () => {
    setLoading(true)
    try {
      const filters = { page, limit: 20 }
      if (filtroCanal !== 'todos') filters.canal = filtroCanal
      if (filtroEstado !== 'todos') filters.estado = filtroEstado

      const response = await getEnvios(filters)
      setEnvios(response.data)

      // Calcular estadísticas sencillas basadas en los registros obtenidos
      // Nota: En producción, esto debería venir del backend dashboard/resumen, pero para
      // rapidez de UI calculamos en base a los registros visibles.
      let enviadosCount = 0
      let pendientesCount = 0
      let fallidosCount = 0

      response.data.forEach(e => {
        if (e.estado === 'enviado') enviadosCount++
        else if (e.estado === 'pendiente') pendientesCount++
        else if (e.estado === 'fallido') fallidosCount++
      })

      setStats({
        enviados: enviadosCount,
        pendientes: pendientesCount,
        fallidos: fallidosCount
      })
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar historial de envíos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEnvios()
  }, [page, filtroCanal, filtroEstado])

  const handleReintentar = async (id) => {
    try {
      notify.info('Reintentando envío...')
      await reintentarEnvio(id)
      notify.success('Envío en proceso de reintento.')
      fetchEnvios()
    } catch (err) {
      console.error(err)
      notify.error('No se pudo reintentar el envío.')
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Summary Stats ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-2xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 flex items-center justify-center">
            <CheckCircle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Entregados Exitosamente</p>
            <p className="text-xl font-bold text-slate-800">{stats.enviados}</p>
          </div>
        </div>

        <div className="p-4 bg-yellow-50 border border-yellow-100 rounded-2xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-600 flex items-center justify-center">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Pendientes de Envío</p>
            <p className="text-xl font-bold text-slate-800">{stats.pendientes}</p>
          </div>
        </div>

        <div className="p-4 bg-red-50 border border-red-100 rounded-2xl flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Envíos Fallidos</p>
            <p className="text-xl font-bold text-slate-800">{stats.fallidos}</p>
          </div>
        </div>
      </div>

      {/* ── Filters bar ────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
            Canal de Envío
          </label>
          <select
            value={filtroCanal}
            onChange={(e) => setFiltroCanal(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
          >
            <option value="todos">Todos</option>
            <option value="email">Email</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
            Estado de Entrega
          </label>
          <select
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
          >
            <option value="todos">Todos</option>
            <option value="enviado">Enviado</option>
            <option value="pendiente">Pendiente</option>
            <option value="fallido">Fallido</option>
          </select>
        </div>
      </div>

      {/* ── Table Section ─────────────────────────────────────── */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">
                <th className="pb-3 font-semibold">Reporte / Folio</th>
                <th className="pb-3 font-semibold">Canal</th>
                <th className="pb-3 font-semibold">Destinatario</th>
                <th className="pb-3 font-semibold">Estado</th>
                <th className="pb-3 font-semibold">Intentos</th>
                <th className="pb-3 font-semibold">Detalle Error</th>
                <th className="pb-3 font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {envios.map((e) => (
                <tr key={e.id} className="text-sm text-slate-600 hover:bg-slate-50/50 transition">
                  <td className="py-3.5 font-semibold text-slate-850">
                    <div className="flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-teal-600" />
                      <span>{e.reporte_folio}</span>
                    </div>
                  </td>
                  <td className="py-3.5">
                    <div className="flex items-center gap-1 text-xs">
                      {e.canal === 'email' ? (
                        <>
                          <Mail className="w-4 h-4 text-blue-500" />
                          <span>Email</span>
                        </>
                      ) : (
                        <>
                          <MessageCircle className="w-4 h-4 text-emerald-500" />
                          <span>WhatsApp</span>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="py-3.5 font-medium">{e.destinatario}</td>
                  <td className="py-3.5">
                    <Badge variant={e.estado}>
                      {e.estado}
                    </Badge>
                  </td>
                  <td className="py-3.5 text-xs font-bold text-slate-500">{e.intentos}</td>
                  <td className="py-3.5 text-xs text-red-500 max-w-[200px] truncate" title={e.error_detalle}>
                    {e.error_detalle || '-'}
                  </td>
                  <td className="py-3.5 text-right">
                    {e.estado === 'fallido' && (
                      <button
                        onClick={() => handleReintentar(e.id)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-teal-600 hover:bg-slate-50 transition inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider"
                        title="Reintentar envío"
                      >
                        <RotateCcw className="w-4 h-4" />
                        <span>Reintentar</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {envios.length === 0 && !loading && (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-400">
                    No se encontraron envíos con los filtros aplicados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
