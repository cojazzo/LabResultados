import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor: attach Bearer token ──────────────────────
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('lab_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: redirect on 401 ─────────────────────────
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('lab_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// ── Auth ───────────────────────────────────────────────────────────
export const login = (username, password) =>
  client.post('/auth/login', new URLSearchParams({ username, password }), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

export const getMe = () => client.get('/auth/me')

// ── Upload / Lotes ────────────────────────────────────────────────
export const uploadExcel = (files) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return client.post('/upload/excel', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getLotes = (page = 1) =>
  client.get('/upload/lotes', { params: { page } })

export const getLote = (id) => client.get(`/upload/lotes/${id}`)

// ── Resultados ────────────────────────────────────────────────────
export const getResultados = (filters = {}) =>
  client.get('/resultados', { params: filters })

export const getResultado = (id) => client.get(`/resultados/${id}`)

// ── Pacientes ─────────────────────────────────────────────────────
export const getPacientes = (search = '') =>
  client.get('/pacientes', { params: { search } })

export const getPacienteResultados = (id) =>
  client.get(`/pacientes/${id}/resultados`)

// ── Reportes ──────────────────────────────────────────────────────
export const generarReporte = (data) =>
  client.post('/reportes/generar', data)

export const generarMasivo = (data) =>
  client.post('/reportes/generar-masivo', data)

export const getReportes = (page = 1) =>
  client.get('/reportes', { params: { page } })

export const descargarReporte = (id) =>
  client.get(`/reportes/${id}/descargar`, { responseType: 'blob' })

// ── Envíos ────────────────────────────────────────────────────────
export const enviarEmail = (data) =>
  client.post('/envios/email', data)

export const enviarWhatsapp = (data) =>
  client.post('/envios/whatsapp', data)

export const getEnvios = (filters = {}) =>
  client.get('/envios', { params: filters })

export const reintentarEnvio = (id) =>
  client.post(`/envios/${id}/reintentar`)

// ── Dashboard ─────────────────────────────────────────────────────
export const getDashboardResumen = (filters = {}) =>
  client.get('/dashboard/resumen', { params: filters })

export const getDashboardTendencia = (params = {}) =>
  client.get('/dashboard/tendencia', { params })

export const getDashboardAnormales = () =>
  client.get('/dashboard/anormales')

export const getDashboardTopPruebas = (limit = 10) =>
  client.get('/dashboard/top-pruebas', { params: { limit } })

export const getDashboardMapaPacientes = () =>
  client.get('/dashboard/mapa-pacientes')

export const geocodificarPacientes = () =>
  client.post('/dashboard/geocodificar')

// ── Catálogo ──────────────────────────────────────────────────────
export const getPruebas = () => client.get('/catalogo/pruebas')

export const createPrueba = (data) =>
  client.post('/catalogo/pruebas', data)

export const updatePrueba = (id, data) =>
  client.put(`/catalogo/pruebas/${id}`, data)


// ── Químicos ──────────────────────────────────────────────────────
export const getQuimicos = () => client.get('/quimicos')
export const getQuimicosActivos = () => client.get('/quimicos/activos')
export const createQuimico = (data) => client.post('/quimicos', data)
export const updateQuimico = (id, data) => client.put(`/quimicos/${id}`, data)

// ── Usuarios (admin) ──────────────────────────────────────────────
export const getUsuarios = () => client.get('/auth/users')
export const createUsuario = (data) => client.post('/auth/register', data)
export const updateUsuario = (id, data) => client.put(`/auth/users/${id}`, data)
export const toggleUsuarioActivo = (id) => client.patch(`/auth/users/${id}/toggle-active`)

export default client
