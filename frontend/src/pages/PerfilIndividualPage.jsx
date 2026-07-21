import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router'
import { User, Activity, Mail, Phone, Calendar, ArrowLeft, Send, CheckCircle2, Edit2, Save, X } from 'lucide-react'
import api from '../api/client.js'
import LoadingSkeleton from '../components/LoadingSkeleton'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'

export default function PerfilIndividualPage() {
  const { id } = useParams()
  const [paciente, setPaciente] = useState(null)
  const [resultados, setResultados] = useState([])
  const [loading, setLoading] = useState(true)
  const [isEditingCuestionario, setIsEditingCuestionario] = useState(false)
  const [editFormData, setEditFormData] = useState({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchPerfil()
  }, [id])

  const fetchPerfil = async () => {
    try {
      setLoading(true)
      // En una app real haríamos 2 llamadas o 1 combinada
      // 1. Datos del paciente
      const pacRes = await api.get(`/pacientes/${id}`)
      setPaciente(pacRes.data)
      
      // 2. Resultados (usando los endpoints existentes de ser posible)
      const resData = await api.get(`/resultados?paciente_id=${id}&limit=100`)
      setResultados(resData.data.items || resData.data)
      
    } catch (error) {
      console.error('Error fetching perfil', error)
    } finally {
      setLoading(false)
    }
  }

  // Agrupar resultados por prueba para la gráfica evolutiva
  // Solo graficamos CRTS por simplicidad o las numéricas
  const chartData = []
  if (resultados.length > 0) {
    const dates = [...new Set(resultados.map(r => r.fecha_toma))].sort()
    
    dates.forEach(date => {
      const dataPoint = { date }
      resultados.filter(r => r.fecha_toma === date).forEach(r => {
        dataPoint[r.prueba.codigo] = parseFloat(r.valor) || null
      })
      chartData.push(dataPoint)
    })
  }

  const autorizarReporte = async () => {
    if(!confirm("¿Autorizar el envío de los resultados a n8n (Puente Outlook)?")) return;
    try {
      const ids = resultados.map(r => r.id).filter(id => id);
      if (ids.length === 0) {
        alert("No hay resultados cargados para enviar.");
        return;
      }
      
      await api.post(`/envios/outlook/trigger`, { resultado_ids: ids })
      alert("Resultados enviados exitosamente a n8n.")
    } catch(e) {
      alert("Error autorizando: " + (e.response?.data?.detail || e.message))
    }
  }

  const handleEditClick = () => {
    setEditFormData({
      peso: paciente.peso || '',
      estatura: paciente.estatura || '',
      tipo_agua: paciente.tipo_agua || '',
      cocina_agua_llave: paciente.cocina_agua_llave || '',
      padecimientos: paciente.padecimientos || '',
      suplemento_detalle: paciente.suplemento_detalle || ''
    })
    setIsEditingCuestionario(true)
  }

  const handleEditChange = (e) => {
    const { name, value } = e.target
    setEditFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSaveCuestionario = async () => {
    try {
      setSaving(true)
      const payload = {
        peso: editFormData.peso ? parseFloat(editFormData.peso) : null,
        estatura: editFormData.estatura ? parseFloat(editFormData.estatura) : null,
        tipo_agua: editFormData.tipo_agua || null,
        cocina_agua_llave: editFormData.cocina_agua_llave || null,
        padecimientos: editFormData.padecimientos || null,
        suplemento_detalle: editFormData.suplemento_detalle || null
      }
      const res = await api.patch(`/pacientes/${id}/cuestionario`, payload)
      setPaciente(res.data)
      setIsEditingCuestionario(false)
    } catch (error) {
      alert("Error guardando los datos: " + (error.response?.data?.detail || error.message))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        <LoadingSkeleton className="h-32 w-full rounded-2xl" />
        <LoadingSkeleton className="h-64 w-full rounded-2xl" />
      </div>
    )
  }

  if (!paciente) return <div className="p-8 text-center">Paciente no encontrado</div>

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div className="flex items-center gap-4">
        <Link to="/perfiles" className="p-2 hover:bg-slate-100 rounded-full transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-600" />
        </Link>
        <h1 className="text-2xl font-bold text-slate-800 flex-1">Expediente Clínico</h1>
        
        <button 
          onClick={autorizarReporte}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-sm font-medium transition-colors shadow-sm"
        >
          <CheckCircle2 className="w-4 h-4" />
          Autorizar Envío (n8n)
        </button>
      </div>

      {/* Tarjeta Info */}
      <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 md:p-8">
        <div className="flex flex-col md:flex-row gap-6 md:gap-8 items-start">
          <div className="w-24 h-24 rounded-full bg-gradient-to-br from-emerald-100 to-teal-100 text-emerald-600 flex items-center justify-center flex-shrink-0 text-3xl font-bold shadow-inner">
            {paciente.nombre?.charAt(0) || 'P'}
          </div>
          <div className="flex-1 space-y-4">
            <div>
              <h2 className="text-2xl font-bold text-slate-800">
                {paciente.nombre} {paciente.apellido} {paciente.apellido_materno || ''}
              </h2>
              <div className="flex flex-wrap gap-3 mt-2 text-sm">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-600 font-mono">
                  {paciente.identificacion}
                </span>
                {paciente.sexo && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-600">
                    <User className="w-3.5 h-3.5" />
                    {paciente.sexo === 'M' ? 'Masculino' : 'Femenino'}
                  </span>
                )}
                {paciente.edad && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-50 text-purple-600">
                    {paciente.edad} años
                  </span>
                )}
              </div>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-slate-600 border-t border-slate-100 pt-4">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-slate-400" />
                {paciente.email || 'Sin correo electrónico'}
                {paciente.email_consent && <CheckCircle2 className="w-3 h-3 text-emerald-500" title="Consentimiento dado" />}
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-slate-400" />
                {paciente.whatsapp || paciente.telefono || 'Sin teléfono'}
                {paciente.whatsapp_consent && <CheckCircle2 className="w-3 h-3 text-emerald-500" title="Consentimiento dado" />}
              </div>
            </div>

            {/* Datos del Cuestionario */}
            <div className="mt-4 pt-4 border-t border-slate-100 text-sm text-slate-600 space-y-2">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-slate-800">Datos Clínicos Adicionales</h3>
                {!isEditingCuestionario ? (
                  <button onClick={handleEditClick} className="text-emerald-600 hover:text-emerald-700 p-1 flex items-center gap-1 text-xs font-medium">
                    <Edit2 className="w-3 h-3" /> Editar
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <button onClick={() => setIsEditingCuestionario(false)} className="text-slate-500 hover:text-slate-700 p-1 flex items-center gap-1 text-xs font-medium" disabled={saving}>
                      <X className="w-3 h-3" /> Cancelar
                    </button>
                    <button onClick={handleSaveCuestionario} className="text-emerald-600 hover:text-emerald-700 p-1 flex items-center gap-1 text-xs font-medium bg-emerald-50 rounded px-2" disabled={saving}>
                      <Save className="w-3 h-3" /> {saving ? 'Guardando...' : 'Guardar'}
                    </button>
                  </div>
                )}
              </div>
              
              {!isEditingCuestionario ? (
                (paciente.peso || paciente.estatura || paciente.padecimientos || paciente.tipo_agua || paciente.suplemento_detalle || paciente.cocina_agua_llave) ? (
                  <div className="grid grid-cols-2 gap-2">
                    {paciente.peso && <div><span className="font-medium">Peso:</span> {paciente.peso} kg</div>}
                    {paciente.estatura && <div><span className="font-medium">Estatura:</span> {paciente.estatura} cm</div>}
                    {paciente.tipo_agua && <div><span className="font-medium">Tipo de Agua:</span> {paciente.tipo_agua}</div>}
                    {paciente.cocina_agua_llave && <div><span className="font-medium">Cocina c/ Llave:</span> {paciente.cocina_agua_llave}</div>}
                    {paciente.padecimientos && <div className="col-span-2"><span className="font-medium">Padecimientos:</span> {paciente.padecimientos}</div>}
                    {paciente.suplemento_detalle && <div className="col-span-2"><span className="font-medium">Suplementos:</span> {paciente.suplemento_detalle}</div>}
                  </div>
                ) : (
                  <div className="text-slate-400 italic">No hay datos clínicos registrados.</div>
                )
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Peso (kg)</label>
                    <input type="number" step="0.1" name="peso" value={editFormData.peso} onChange={handleEditChange} className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Estatura (cm)</label>
                    <input type="number" step="0.1" name="estatura" value={editFormData.estatura} onChange={handleEditChange} className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Tipo de Agua</label>
                    <input type="text" name="tipo_agua" value={editFormData.tipo_agua} onChange={handleEditChange} className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Cocina c/ Llave</label>
                    <input type="text" name="cocina_agua_llave" value={editFormData.cocina_agua_llave} onChange={handleEditChange} className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500" />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-medium text-slate-500 mb-1">Padecimientos</label>
                    <textarea name="padecimientos" value={editFormData.padecimientos} onChange={handleEditChange} rows={2} className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 resize-none" />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-medium text-slate-500 mb-1">Suplementos</label>
                    <textarea name="suplemento_detalle" value={editFormData.suplemento_detalle} onChange={handleEditChange} rows={2} className="w-full px-3 py-1.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 resize-none" />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Gráfica Evolutiva */}
      <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
          <Activity className="w-5 h-5 text-emerald-500" />
          Evolución Histórica
        </h3>
        
        {chartData.length > 1 ? (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend />
                <Line type="monotone" dataKey="CRTS" stroke="#10b981" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} name="Creatinina" />
                <Line type="monotone" dataKey="ALBOR" stroke="#6366f1" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} name="Microalbúmina" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-40 flex items-center justify-center text-slate-400 bg-slate-50 rounded-xl">
            Insuficientes datos para graficar evolución (requiere &gt; 1 visita).
          </div>
        )}
      </div>

      {/* Tabla Histórica */}
      <div className="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-800">Resultados Detallados</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-slate-50 text-slate-500 font-medium">
              <tr>
                <th className="px-6 py-3">Fecha</th>
                <th className="px-6 py-3">Prueba</th>
                <th className="px-6 py-3">Valor</th>
                <th className="px-6 py-3">Referencia</th>
                <th className="px-6 py-3">Interpretación</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {resultados.map((res, i) => (
                <tr key={res.id || i} className="hover:bg-slate-50/50">
                  <td className="px-6 py-3 text-slate-600">{res.fecha_toma}</td>
                  <td className="px-6 py-3 font-medium text-slate-800">{res.prueba.nombre}</td>
                  <td className="px-6 py-3">
                    <span className="font-mono">{res.valor_texto || res.valor}</span> {res.prueba.unidad}
                  </td>
                  <td className="px-6 py-3 text-slate-500">
                    {res.prueba.valor_min} - {res.prueba.valor_max}
                  </td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      res.interpretacion === 'normal' ? 'bg-emerald-50 text-emerald-700' :
                      ['alto', 'bajo'].includes(res.interpretacion) ? 'bg-amber-50 text-amber-700' :
                      'bg-red-50 text-red-700'
                    }`}>
                      {res.interpretacion?.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
              {resultados.length === 0 && (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-slate-500">
                    No hay resultados cargados.
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
