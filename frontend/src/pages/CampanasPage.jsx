import { useState, useEffect } from 'react'
import { Plus, Users, Search, Calendar as CalendarIcon, CheckCircle, Clock, Edit2 } from 'lucide-react'
import { getCampanas, createCampana, getCampanaPacientes, updateCampana } from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'
import LoadingSkeleton from '../components/LoadingSkeleton.jsx'
import Modal from '../components/Modal.jsx'
import Badge from '../components/Badge.jsx'

export default function CampanasPage() {
  const notify = useNotification()
  const [campanas, setCampanas] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')

  // Modal para crear/editar campaña
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({
    nombre: '',
    tipo: 'secundaria',
    fecha_inicio: '',
    fecha_fin: '',
    estado: 'planificada'
  })
  const [saving, setSaving] = useState(false)

  // Modal para ver pacientes
  const [showPacientesModal, setShowPacientesModal] = useState(false)
  const [selectedCampana, setSelectedCampana] = useState(null)
  const [pacientes, setPacientes] = useState([])
  const [loadingPacientes, setLoadingPacientes] = useState(false)

  const fetchCampanas = async () => {
    setLoading(true)
    try {
      const res = await getCampanas()
      setCampanas(res.data)
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar campañas')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCampanas()
  }, [])

  const handleOpenCreateModal = () => {
    setIsEditing(false)
    setEditingId(null)
    setFormData({
      nombre: '',
      tipo: 'secundaria',
      fecha_inicio: '',
      fecha_fin: '',
      estado: 'planificada'
    })
    setShowCreateModal(true)
  }

  const handleOpenEditModal = (campana) => {
    setIsEditing(true)
    setEditingId(campana.id)
    setFormData({
      nombre: campana.nombre,
      tipo: campana.tipo,
      fecha_inicio: campana.fecha_inicio || '',
      fecha_fin: campana.fecha_fin || '',
      estado: campana.estado
    })
    setShowCreateModal(true)
  }

  const handleSaveCampana = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (isEditing) {
        await updateCampana(editingId, formData)
        notify.success('Campaña actualizada exitosamente')
      } else {
        await createCampana(formData)
        notify.success('Campaña creada exitosamente')
      }
      setShowCreateModal(false)
      fetchCampanas()
    } catch (err) {
      console.error(err)
      notify.error(err.response?.data?.detail || 'Error al guardar la campaña')
    } finally {
      setSaving(false)
    }
  }

  const handleOpenPacientes = async (campana) => {
    setSelectedCampana(campana)
    setShowPacientesModal(true)
    setLoadingPacientes(true)
    try {
      const res = await getCampanaPacientes(campana.id)
      setPacientes(res.data)
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar los pacientes de la campaña')
    } finally {
      setLoadingPacientes(false)
    }
  }

  const filteredCampanas = campanas.filter(c =>
    c.nombre.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getTipoLabel = (tipo) => {
    switch(tipo) {
      case 'secundaria': return 'Secundaria'
      case 'servicio_externo': return 'Servicio Externo'
      case 'campana_externa': return 'Campaña Externa'
      default: return tipo
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Campañas</h1>
          <p className="text-slate-500 text-sm">Gestiona campañas secundarias, servicios externos y campañas externas</p>
        </div>
        <button
          onClick={handleOpenCreateModal}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition font-medium"
        >
          <Plus className="w-5 h-5" />
          Nueva Campaña
        </button>
      </div>

      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Buscar campaña por nombre..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:bg-white transition-colors outline-none"
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-4">
            <LoadingSkeleton className="h-16 w-full" />
            <LoadingSkeleton className="h-16 w-full" />
            <LoadingSkeleton className="h-16 w-full" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider bg-slate-50/50">
                  <th className="p-4 font-semibold">Nombre</th>
                  <th className="p-4 font-semibold">Tipo</th>
                  <th className="p-4 font-semibold">Fechas</th>
                  <th className="p-4 font-semibold">Estado</th>
                  <th className="p-4 font-semibold text-center">Pacientes</th>
                  <th className="p-4 font-semibold text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredCampanas.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="p-12 text-center text-slate-500">
                      <CalendarIcon className="w-12 h-12 mx-auto text-slate-300 mb-3" />
                      <p>No se encontraron campañas.</p>
                    </td>
                  </tr>
                ) : (
                  filteredCampanas.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                      <td className="p-4">
                        <div className="font-semibold text-slate-800">{c.nombre}</div>
                      </td>
                      <td className="p-4">
                        <span className="text-sm text-slate-600">{getTipoLabel(c.tipo)}</span>
                      </td>
                      <td className="p-4">
                        <div className="text-xs text-slate-500 flex flex-col gap-1">
                          <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-emerald-500" /> {new Date(c.fecha_inicio).toLocaleDateString('es-MX')}</span>
                          {c.fecha_fin && <span className="flex items-center gap-1"><Clock className="w-3 h-3 text-orange-500" /> {new Date(c.fecha_fin).toLocaleDateString('es-MX')}</span>}
                        </div>
                      </td>
                      <td className="p-4">
                        <Badge variant={c.estado === 'activa' ? 'normal' : c.estado === 'cerrada' ? 'critico' : 'parcial'}>
                          {c.estado.charAt(0).toUpperCase() + c.estado.slice(1)}
                        </Badge>
                      </td>
                      <td className="p-4 text-center">
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 rounded-lg text-sm font-semibold text-slate-700">
                          <Users className="w-4 h-4 text-slate-400" />
                          {c.total_pacientes || 0}
                        </div>
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleOpenPacientes(c)}
                            className="px-3 py-1.5 bg-teal-50 text-teal-700 hover:bg-teal-100 rounded-lg text-sm font-medium transition"
                          >
                            Ver Pacientes
                          </button>
                          <button
                            onClick={() => handleOpenEditModal(c)}
                            className="p-1.5 text-slate-400 hover:text-teal-600 hover:bg-teal-50 rounded-lg transition"
                            title="Editar Campaña"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal Crear/Editar Campaña */}
      <Modal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={isEditing ? "Editar Campaña" : "Nueva Campaña"}
        size="md"
      >
        <form onSubmit={handleSaveCampana} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Nombre de la Campaña</label>
            <input
              type="text"
              required
              value={formData.nombre}
              onChange={(e) => setFormData({...formData, nombre: e.target.value})}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition"
              placeholder="Ej. Tamizaje Escolar 2024"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Tipo</label>
            <select
              value={formData.tipo}
              onChange={(e) => setFormData({...formData, tipo: e.target.value})}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition bg-white"
            >
              <option value="secundaria">Secundaria</option>
              <option value="servicio_externo">Servicio Externo</option>
              <option value="campana_externa">Campaña Externa</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700">Fecha de Inicio</label>
              <input
                type="date"
                required
                value={formData.fecha_inicio}
                onChange={(e) => setFormData({...formData, fecha_inicio: e.target.value})}
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700">Fecha de Fin (Opcional)</label>
              <input
                type="date"
                value={formData.fecha_fin}
                onChange={(e) => setFormData({...formData, fecha_fin: e.target.value})}
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700">Estado</label>
            <select
              value={formData.estado}
              onChange={(e) => setFormData({...formData, estado: e.target.value})}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 outline-none transition bg-white"
            >
              <option value="planificada">Planificada</option>
              <option value="activa">Activa</option>
              <option value="cerrada">Cerrada</option>
            </select>
          </div>

          <div className="pt-4 flex gap-3 justify-end">
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="px-4 py-2 bg-slate-100 text-slate-700 font-medium rounded-xl hover:bg-slate-200 transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition disabled:opacity-70 flex items-center gap-2"
            >
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal Ver Pacientes */}
      <Modal
        open={showPacientesModal}
        onClose={() => setShowPacientesModal(false)}
        title={`Pacientes - ${selectedCampana?.nombre}`}
        size="lg"
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          {loadingPacientes ? (
            <div className="space-y-2">
              <LoadingSkeleton className="h-12 w-full" />
              <LoadingSkeleton className="h-12 w-full" />
            </div>
          ) : pacientes.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              <Users className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              <p>No hay pacientes inscritos en esta campaña.</p>
            </div>
          ) : (
            <div className="border border-slate-100 rounded-xl overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 text-xs uppercase tracking-wider font-bold">
                  <tr>
                    <th className="px-4 py-3">Nombre</th>
                    <th className="px-4 py-3">Identificación</th>
                    <th className="px-4 py-3">Fecha Registro</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {pacientes.map(p => (
                    <tr key={p.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium">
                        {p.nombre} {p.apellido} {p.apellido_materno || ''}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">
                        {p.identificacion}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">
                        {new Date(p.created_at).toLocaleString('es-MX')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
