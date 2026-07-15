import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router'
import { login, getMe } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useNotification } from '../context/NotificationContext.jsx'
import { FlaskConical, Lock, User, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { loginUser } = useAuth()
  const notify = useNotification()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/'

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) {
      notify.error('Por favor, ingresa usuario y contraseña.')
      return
    }

    setLoading(true)
    try {
      const response = await login(username, password)
      const { access_token } = response.data
      
      // Obtener datos del usuario
      localStorage.setItem('lab_token', access_token)
      const userRes = await getMe()
      
      loginUser(access_token, userRes.data)
      notify.success('Sesión iniciada correctamente.')
      navigate(from, { replace: true })
    } catch (err) {
      console.error(err)
      notify.error(err.response?.data?.detail || 'Error al iniciar sesión. Verifica tus credenciales.')
      localStorage.removeItem('lab_token')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-900 bg-gradient-to-tr from-slate-950 via-slate-900 to-teal-950">
      <div className="w-full max-w-md p-8 mx-4 bg-white/10 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl">
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-teal-500/20 border border-teal-500/30 text-teal-400 mb-4 animate-pulse">
            <FlaskConical className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">LabResultados</h2>
          <p className="text-sm text-slate-400 mt-1">Ingresa al portal de administración</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Usuario
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <User className="w-5 h-5" />
              </span>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Nombre de usuario"
                className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-slate-700/50 text-white rounded-xl placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500 transition duration-200"
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Contraseña
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Lock className="w-5 h-5" />
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-slate-700/50 text-white rounded-xl placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-500 transition duration-200"
                disabled={loading}
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-600 hover:to-emerald-600 text-white font-semibold rounded-xl shadow-lg shadow-teal-500/20 active:scale-98 transition duration-200 flex items-center justify-center gap-2"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Iniciando sesión...</span>
              </>
            ) : (
              <span>Entrar</span>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-white/5 text-center text-xs text-slate-500">
          Laboratorio Clínico &copy; 2026
        </div>
      </div>
    </div>
  )
}
