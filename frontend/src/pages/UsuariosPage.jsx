import { useState, useEffect } from 'react'
import {
  Search, UserCog, Plus, Pencil, ShieldAlert,
  X, Eye, EyeOff, ToggleLeft, ToggleRight, BadgeCheck,
} from 'lucide-react'
import { getUsuarios, createUsuario, updateUsuario, toggleUsuarioActivo } from '../api/client.js'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router'

const ROL_LABELS = {
  admin: { label: 'Administrador', color: 'bg-violet-100 text-violet-700' },
  tecnico: { label: 'Técnico', color: 'bg-sky-100 text-sky-700' },
  quimico: { label: 'Químico', color: 'bg-teal-100 text-teal-700' },
}

const EMPTY_FORM = {
  username: '',
  email: '',
  nombre_completo: '',
  rol: 'tecnico',
  password: '',
}

export default function UsuariosPage() {
  const { user: currentUser } = useAuth()
  const navigate = useNavigate()

  const [usuarios, setUsuarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  // Redirect non-admins immediately
  useEffect(() => {
    if (currentUser && currentUser.rol !== 'admin') {
      navigate('/')
    }
  }, [currentUser, navigate])

  useEffect(() => {
    if (currentUser?.rol === 'admin') {
      fetchUsuarios()
    }
  }, [currentUser])

  const fetchUsuarios = async () => {
    try {
      setLoading(true)
      const res = await getUsuarios()
      setUsuarios(res.data)
    } catch (err) {
      console.error('Error cargando usuarios:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenModal = (usuario = null) => {
    setError(null)
    setShowPassword(false)
    if (usuario) {
      setEditingUser(usuario)
      setFormData({
        username: usuario.username,
        email: usuario.email,
        nombre_completo: usuario.nombre_completo,
        rol: usuario.rol,
        password: '',
      })
    } else {
      setEditingUser(null)
      setFormData(EMPTY_FORM)
    }
    setShowModal(true)
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (editingUser) {
        const payload = {
          email: formData.email,
          nombre_completo: formData.nombre_completo,
          rol: formData.rol,
        }
        if (formData.password) payload.password = formData.password
        await updateUsuario(editingUser.id, payload)
      } else {
        await createUsuario(formData)
      }
      setShowModal(false)
      fetchUsuarios()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al guardar el usuario')
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async (usuario) => {
    try {
      await toggleUsuarioActivo(usuario.id)
      fetchUsuarios()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al cambiar el estado del usuario')
    }
  }

  const filtered = usuarios.filter(
    (u) =>
      u.nombre_completo.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.email.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  // Guard for non-admins (also shown while redirect takes effect)
  if (currentUser && currentUser.rol !== 'admin') {
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Gestión de Usuarios</h1>
          <p className="text-slate-500 text-sm">Crea y administra las cuentas de acceso al sistema</p>
        </div>
        <button
          id="btn-nuevo-usuario"
          onClick={() => handleOpenModal()}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-xl hover:bg-emerald-700 transition font-medium shadow-sm"
        >
          <Plus className="w-5 h-5" />
          Nuevo Usuario
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {[
          { label: 'Total', count: usuarios.length, color: 'text-slate-700', bg: 'bg-slate-100' },
          { label: 'Activos', count: usuarios.filter(u => u.is_active).length, color: 'text-emerald-700', bg: 'bg-emerald-50' },
          { label: 'Inactivos', count: usuarios.filter(u => !u.is_active).length, color: 'text-red-600', bg: 'bg-red-50' },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={`${bg} rounded-2xl px-5 py-4`}>
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{count}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
          <input
            id="input-buscar-usuario"
            type="text"
            placeholder="Buscar por nombre, usuario o correo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:bg-white transition-colors outline-none"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-4">
            <LoadingSkeleton className="h-16 w-full" />
            <LoadingSkeleton className="h-16 w-full" />
            <LoadingSkeleton className="h-16 w-full" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <UserCog className="w-12 h-12 mx-auto text-slate-300 mb-3" />
            <p>No se encontraron usuarios.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filtered.map((u) => {
              const rolMeta = ROL_LABELS[u.rol] || { label: u.rol, color: 'bg-slate-100 text-slate-600' }
              const isSelf = u.id === currentUser?.id
              return (
                <div
                  key={u.id}
                  className={`flex flex-col sm:flex-row sm:items-center justify-between p-4 transition-colors ${u.is_active ? 'hover:bg-slate-50' : 'bg-slate-50/60 opacity-70'}`}
                >
                  {/* Avatar + info */}
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 font-bold text-sm ${
                        u.is_active
                          ? 'bg-gradient-to-br from-emerald-400 to-teal-600 text-white'
                          : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      {u.nombre_completo?.charAt(0)?.toUpperCase() || 'U'}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-slate-800 text-sm">{u.nombre_completo}</h3>
                        {isSelf && (
                          <span className="inline-flex items-center gap-1 text-[10px] bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 font-semibold">
                            <BadgeCheck className="w-3 h-3" /> Tú
                          </span>
                        )}
                        <span className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full ${rolMeta.color}`}>
                          {rolMeta.label}
                        </span>
                        {!u.is_active && (
                          <span className="inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-600">
                            Inactivo
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5 truncate">
                        @{u.username} · {u.email}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-3 sm:mt-0 flex items-center gap-2 justify-end">
                    <button
                      onClick={() => handleOpenModal(u)}
                      title="Editar usuario"
                      className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleToggleActive(u)}
                      disabled={isSelf}
                      title={u.is_active ? 'Desactivar usuario' : 'Activar usuario'}
                      className={`p-2 rounded-lg transition-colors ${
                        isSelf
                          ? 'text-slate-200 cursor-not-allowed'
                          : u.is_active
                          ? 'text-slate-400 hover:text-red-500 hover:bg-red-50'
                          : 'text-slate-400 hover:text-emerald-600 hover:bg-emerald-50'
                      }`}
                    >
                      {u.is_active ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Modal header */}
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <h3 className="font-bold text-lg text-slate-800">
                {editingUser ? 'Editar Usuario' : 'Nuevo Usuario'}
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

              {/* Nombre completo */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Nombre completo</label>
                <input
                  id="input-nombre-usuario"
                  type="text"
                  required
                  value={formData.nombre_completo}
                  onChange={(e) => setFormData({ ...formData, nombre_completo: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none"
                  placeholder="Ej. María García López"
                />
              </div>

              {/* Username (solo en creación) */}
              {!editingUser && (
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-700">
                    Nombre de usuario <span className="text-slate-400 font-normal">(no se puede cambiar)</span>
                  </label>
                  <input
                    id="input-username"
                    type="text"
                    required
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value.toLowerCase().replace(/\s/g, '') })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none font-mono"
                    placeholder="Ej. mgarcia"
                  />
                </div>
              )}

              {/* Email */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Correo electrónico</label>
                <input
                  id="input-email-usuario"
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none"
                  placeholder="correo@lab.com"
                />
              </div>

              {/* Rol */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Rol</label>
                <select
                  id="select-rol-usuario"
                  value={formData.rol}
                  onChange={(e) => setFormData({ ...formData, rol: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none"
                >
                  <option value="tecnico">Técnico</option>
                  <option value="quimico">Químico</option>
                  <option value="admin">Administrador</option>
                </select>
                <p className="text-xs text-slate-400">
                  {formData.rol === 'admin' && 'Acceso completo al sistema, incluida la gestión de usuarios.'}
                  {formData.rol === 'tecnico' && 'Puede cargar archivos, consultar resultados y enviar reportes.'}
                  {formData.rol === 'quimico' && 'Acceso a resultados y reportes. Puede validar análisis.'}
                </p>
              </div>

              {/* Contraseña */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">
                  {editingUser ? 'Nueva contraseña (dejar en blanco para no cambiar)' : 'Contraseña'}
                </label>
                <div className="relative">
                  <input
                    id="input-password-usuario"
                    type={showPassword ? 'text' : 'password'}
                    required={!editingUser}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full px-3 py-2 pr-10 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 focus:bg-white transition-colors outline-none"
                    placeholder={editingUser ? '(sin cambios)' : 'Mínimo 8 caracteres'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Buttons */}
              <div className="pt-2 flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 bg-slate-100 text-slate-700 font-medium rounded-xl hover:bg-slate-200 transition"
                >
                  Cancelar
                </button>
                <button
                  id="btn-guardar-usuario"
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 transition disabled:opacity-70"
                >
                  {saving ? 'Guardando...' : editingUser ? 'Guardar Cambios' : 'Crear Usuario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
