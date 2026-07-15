import { useState, useEffect } from 'react'
import { Search, Users, Plus, Pencil, Check, X, ShieldAlert } from 'lucide-react'
import { getQuimicos, createQuimico, updateQuimico } from '../api/client.js'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router'

export default function QuimicosPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [quimicos, setQuimicos] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  
  const [showModal, setShowModal] = useState(false)
  const [editingQuimico, setEditingQuimico] = useState(null)
  
  const [formData, setFormData] = useState({
    nombre_completo: '',
    cedula: '',
    activo: true
  })
  
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (user && user.rol !== 'admin') {
      navigate('/')
      return
    }
    fetchQuimicos()
  }, [user, navigate])

  const fetchQuimicos = async () => {
    try {
      setLoading(true)
      const res = await getQuimicos()
      setQuimicos(res.data)
    } catch (error) {
      console.error('Error cargando quimicos:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenModal = (quimico = null) => {
    setError(null)
    if (quimico) {
      setEditingQuimico(quimico)
      setFormData({
        nombre_completo: quimico.nombre_completo,
        cedula: quimico.cedula,
        activo: quimico.activo
      })
    } else {
      setEditingQuimico(null)
      setFormData({
        nombre_completo: '',
        cedula: '',
        activo: true
      })
    }
    setShowModal(true)
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (editingQuimico) {
        await updateQuimico(editingQuimico.id, formData)
      } else {
        await createQuimico(formData)
      }
      setShowModal(false)
      fetchQuimicos()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al guardar el químico')
    } finally {
      setSaving(false)
    }
  }

  const filteredQuimicos = quimicos.filter(q => 
    q.nombre_completo.toLowerCase().includes(searchTerm.toLowerCase()) ||
    q.cedula.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (user && user.rol !== 'admin') {
    return (
      <div className="flex flex-col items-center justify-center h-[70vh]">
        <ShieldAlert className="w-16 h-16 text-red-500 mb-4" />
        <h2 className="text-2xl font-bold text-slate-800 mb-2">Acceso Denegado</h2>
        <p className="text-slate-500">No tienes permisos para acceder a esta sección.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Químicos Validadores</h1>
          <p className="text-slate-500 text-sm">Gestiona los químicos que firman los reportes de resultados</p>
        </div>
        <button
          onClick={() => handleOpenModal()}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 transition font-medium"
        >
          <Plus className="w-5 h-5" />
          Nuevo Químico
        </button>
      </div>

      {/* Barra de búsqueda */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Buscar por nombre o cédula..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:bg-white transition-colors outline-none"
          />
        </div>
      </div>

      {/* Lista de químicos */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-4">
             <LoadingSkeleton className="h-16 w-full" />
             <LoadingSkeleton className="h-16 w-full" />
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredQuimicos.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <Users className="w-12 h-12 mx-auto text-slate-300 mb-3" />
                <p>No se encontraron químicos.</p>
              </div>
            ) : (
              filteredQuimicos.map((quimico) => (
                <div key={quimico.id} className="flex flex-col sm:flex-row sm:items-center justify-between p-4 hover:bg-slate-50 transition-colors group">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 font-bold ${quimico.activo ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-400'}`}>
                      {quimico.nombre_completo.charAt(0)}
                    </div>
                    <div>
                      <h3 className={`font-medium ${quimico.activo ? 'text-slate-800' : 'text-slate-500'}`}>
                        {quimico.nombre_completo}
                      </h3>
                      <p className="text-sm text-slate-500 flex items-center gap-2">
                        <span className="font-mono bg-slate-100 px-1.5 rounded text-xs">Cédula: {quimico.cedula}</span>
                        {quimico.activo ? (
                          <span className="text-emerald-600 flex items-center text-xs gap-1"><Check className="w-3 h-3"/> Activo</span>
                        ) : (
                          <span className="text-slate-400 flex items-center text-xs gap-1"><X className="w-3 h-3"/> Inactivo</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 sm:mt-0 flex items-center justify-end gap-2">
                    <button
                      onClick={() => handleOpenModal(quimico)}
                      className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                      title="Editar"
                    >
                      <Pencil className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Modal CRUD */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <h3 className="font-bold text-lg text-slate-800">
                {editingQuimico ? 'Editar Químico' : 'Nuevo Químico'}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleSave} className="p-5 space-y-4">
              {error && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded-xl border border-red-100 flex gap-2 items-start">
                  <ShieldAlert className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Nombre Completo</label>
                <input
                  type="text"
                  required
                  value={formData.nombre_completo}
                  onChange={(e) => setFormData({...formData, nombre_completo: e.target.value})}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none"
                  placeholder="Ej. Q.F.B. Juan Pérez Gómez"
                />
              </div>
              
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Cédula Profesional</label>
                <input
                  type="text"
                  required
                  value={formData.cedula}
                  onChange={(e) => setFormData({...formData, cedula: e.target.value})}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none font-mono"
                  placeholder="Ej. 1234567"
                />
              </div>
              
              <div className="pt-2">
                <label className="flex items-center gap-3 cursor-pointer">
                  <div className="relative">
                    <input 
                      type="checkbox" 
                      className="sr-only" 
                      checked={formData.activo}
                      onChange={(e) => setFormData({...formData, activo: e.target.checked})}
                    />
                    <div className={`block w-10 h-6 rounded-full transition-colors ${formData.activo ? 'bg-emerald-500' : 'bg-slate-300'}`}></div>
                    <div className={`absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${formData.activo ? 'translate-x-4' : ''}`}></div>
                  </div>
                  <div className="text-sm font-medium text-slate-700">
                    {formData.activo ? 'Activo (Puede firmar reportes)' : 'Inactivo (No aparecerá en la lista)'}
                  </div>
                </label>
              </div>
              
              <div className="pt-4 flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 bg-slate-100 text-slate-700 font-medium rounded-xl hover:bg-slate-200 transition"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 transition disabled:opacity-70"
                >
                  {saving ? 'Guardando...' : 'Guardar Químico'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
