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
    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('lab_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
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

export const uploadTamizajeExcel = (files, campanaId = null) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  let url = '/upload/tamizaje'
  if (campanaId) url += `?campana_id=${campanaId}`
  return client.post(url, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const uploadSecundarias = (files, campanaId) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return client.post(`/upload/secundarias?campana_id=${campanaId}`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const uploadUC1000 = (files) => {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return client.post('/upload/uc1000', fd, {
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

export const exportarReporteExcel = (fechaInicio, fechaFin, campos, pruebaIds, campanaId) => {
  const params = {}
  if (fechaInicio) params.fecha_inicio = fechaInicio
  if (fechaFin) params.fecha_fin = fechaFin
  if (campos && campos.length > 0) params.campos = campos.join(',')
  if (pruebaIds && pruebaIds.length > 0) params.prueba_ids = pruebaIds.join(',')
  if (campanaId) params.campana_id = campanaId
  return client.get('/reportes/exportar-excel', { params, responseType: 'blob' })
}

export const descargarTemplateExcel = () =>
  client.get('/upload/template-excel', { responseType: 'blob' })

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

export const getDashboardMapaHexbin = () =>
  client.get('/dashboard/mapa-hexbin')

export const geocodificarPacientes = () =>
  client.post('/dashboard/geocodificar')

// ── Catálogo ──────────────────────────────────────────────────────
export const getPruebas = () => client.get('/catalogo/pruebas')

export const createPrueba = (data) =>
  client.post('/catalogo/pruebas', data)

export const updatePrueba = (id, data) =>
  client.put(`/catalogo/pruebas/${id}`, data)


// ── Campañas ────────────────────────────────────────────────────────
export const getCampanas = (filters = {}) => client.get('/campanas', { params: filters })
export const getCampana = (id) => client.get(`/campanas/${id}`)
export const createCampana = (data) => client.post('/campanas', data)
export const updateCampana = (id, data) => client.patch(`/campanas/${id}`, data)
export const getCampanaPacientes = (id, params = {}) => client.get(`/campanas/${id}/pacientes`, { params })
export const descargarReportesPdfCampana = (id) =>
  client.get(`/campanas/${id}/reportes-pdf`, { responseType: 'blob' })
export const getCampanasStatsPorOrigen = () => client.get('/campanas/stats/por-origen')

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
