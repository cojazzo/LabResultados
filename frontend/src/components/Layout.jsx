import { useState } from 'react'
import { NavLink, useLocation } from 'react-router'
import { useAuth } from '../context/AuthContext.jsx'
import {
  FlaskConical,
  LayoutDashboard,
  FileSpreadsheet,
  ClipboardList,
  Send,
  BookOpen,
  LogOut,
  Menu,
  X,
  User,
  Users,
  ChevronRight,
} from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Cargar Excel', icon: FileSpreadsheet },
  { to: '/resultados', label: 'Resultados', icon: ClipboardList },
  { to: '/envios', label: 'Envíos', icon: Send },
  { to: '/catalogo', label: 'Catálogo', icon: BookOpen },
  { to: '/perfiles', label: 'Perfiles', icon: Users },
  { to: '/quimicos', label: 'Químicos', icon: Users, reqAdmin: true },
  { to: '/usuarios', label: 'Usuarios', icon: User, reqAdmin: true },
]

const pageTitles = {
  '/': 'Dashboard',
  '/upload': 'Cargar Archivo Excel',
  '/resultados': 'Resultados de Laboratorio',
  '/envios': 'Historial de Envíos',
  '/catalogo': 'Catálogo de Pruebas',
  '/perfiles': 'Perfiles de Pacientes',
  '/quimicos': 'Químicos Validadores',
  '/usuarios': 'Gestión de Usuarios',
}

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pageTitle = pageTitles[location.pathname] || 'LabResultados'

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-bg)]">
      {/* ── Mobile overlay ─────────────────────────────────────── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ────────────────────────────────────────────── */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-64 flex flex-col
          bg-[var(--color-sidebar)] text-white
          transition-transform duration-300 ease-in-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Brand */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-white/10">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-white/15 backdrop-blur-sm">
            <FlaskConical className="w-5 h-5 text-emerald-300" />
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight tracking-tight">LabResultados</h1>
            <p className="text-[10px] uppercase tracking-[.2em] text-white/50 font-medium">
              Sistema de Gestión
            </p>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="ml-auto lg:hidden p-1 rounded-lg hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon, reqAdmin }) => {
            if (reqAdmin && user?.rol !== 'admin') return null;
            return (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `group flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-white/15 text-white shadow-lg shadow-black/10'
                      : 'text-white/60 hover:bg-white/8 hover:text-white'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={`w-[18px] h-[18px] flex-shrink-0 transition-colors ${isActive ? 'text-emerald-300' : 'text-white/40 group-hover:text-white/70'}`} />
                    <span className="flex-1">{label}</span>
                    {isActive && (
                      <ChevronRight className="w-4 h-4 text-white/40" />
                    )}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* User footer */}
        <div className="border-t border-white/10 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-full bg-gradient-to-br from-emerald-400 to-teal-600 text-white text-sm font-bold flex-shrink-0">
              {user?.nombre_completo?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {user?.nombre_completo || 'Usuario'}
              </p>
              <p className="text-xs text-white/40 truncate">
                {user?.email || user?.username || ''}
              </p>
            </div>
            <button
              onClick={logout}
              title="Cerrar sesión"
              className="p-2 rounded-lg text-white/40 hover:text-red-400 hover:bg-white/10 transition-all duration-200"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main area ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="sticky top-0 z-30 flex items-center gap-4 px-6 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200/60">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 -ml-2 rounded-lg text-slate-500 hover:bg-slate-100 transition"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h2 className="text-lg font-semibold text-slate-800">{pageTitle}</h2>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-sm text-slate-500">
              <User className="w-4 h-4" />
              <span>{user?.nombre_completo || 'Usuario'}</span>
            </div>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
