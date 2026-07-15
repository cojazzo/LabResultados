import { useState, useEffect } from 'react'
import {
  getResultados,
  getPruebas,
  getMedicos,
  getQuimicosActivos,
  generarReporte,
  enviarEmail,
  enviarWhatsapp,
  descargarReporte,
} from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'
import {
  FileText,
  Mail,
  Send,
  Search,
  Loader2,
  CheckSquare,
  Square,
  CheckCircle,
  Eye,
} from 'lucide-react'
import Badge from '../components/Badge.jsx'
import Modal from '../components/Modal.jsx'
import Pagination from '../components/Pagination.jsx'

// Helper para agrupar resultados individuales en visitas (Paciente + Fecha Toma)
const groupResultadosIntoVisitas = (items) => {
  const map = {}
  items.forEach(r => {
    const key = `${r.paciente.id}_${r.fecha_toma}`
    if (!map[key]) {
      map[key] = {
        key: key,
        paciente: r.paciente,
        fecha_toma: r.fecha_toma,
        medico: r.medico,
        estudios: [],
        resultadoIds: [],
        interpretacionMaxima: 'normal',
      }
    }
    map[key].estudios.push(r)
    map[key].resultadoIds.push(r.id)

    // Determinar la interpretación más severa de la visita
    const int = r.interpretacion
    const currentMax = map[key].interpretacionMaxima
    if (int === 'critico_alto' || int === 'critico_bajo') {
      map[key].interpretacionMaxima = 'critico'
    } else if (int === 'alto' || int === 'bajo') {
      if (currentMax !== 'critico') {
        map[key].interpretacionMaxima = int
      }
    }
  })
  return Object.values(map)
}

export default function ResultadosPage() {
  const notify = useNotification()
  
  const [visitas, setVisitas] = useState([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  
  // Catálogos para filtros y generación
  const [pruebas, setPruebas] = useState([])
  const [medicos, setMedicos] = useState([])
  const [quimicos, setQuimicos] = useState([])
  
  // Quimico seleccionado para generación de reportes
  const [quimicoGeneracion, setQuimicoGeneracion] = useState('')
  
  // Filtros seleccionados
  const [filtroPaciente, setFiltroPaciente] = useState('')
  const [filtroPrueba, setFiltroPrueba] = useState('')
  const [filtroMedico, setFiltroMedico] = useState('')
  const [filtroFechaDesde, setFiltroFechaDesde] = useState('')
  const [filtroFechaHasta, setFiltroFechaHasta] = useState('')
  const [filtroInterpretacion, setFiltroInterpretacion] = useState('todos')

  // Selección múltiple de visitas
  const [selectedVisitaKeys, setSelectedVisitaKeys] = useState([])
  
  // Modales de envío
  const [emailModalOpen, setEmailModalOpen] = useState(false)
  const [whatsappModalOpen, setWhatsappModalOpen] = useState(false)
  const [activeReporteId, setActiveReporteId] = useState(null)
  
  // Inputs de envío
  const [destinatarioEmail, setDestinatarioEmail] = useState('')
  const [copiaMedico, setCopiaMedico] = useState(false)
  const [destinatarioWhatsapp, setDestinatarioWhatsapp] = useState('')
  const [enviando, setEnviando] = useState(false)

  // Preview de Visita Modal
  const [previewVisita, setPreviewVisita] = useState(null)
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [previewTab, setPreviewTab] = useState('clinical') // 'clinical' o 'pdf'
  const [previewPdfUrl, setPreviewPdfUrl] = useState('')
  const [previewPdfLoading, setPreviewPdfLoading] = useState(false)
  const [reporteId, setReporteId] = useState(null)
  const [reporteGenerando, setReporteGenerando] = useState(false)

  const fetchCatalogos = async () => {
    try {
      const [resPruebas, resMedicos, resQuimicos] = await Promise.all([
        getPruebas(),
        getMedicos(),
        getQuimicosActivos()
      ])
      setPruebas(resPruebas.data)
      setMedicos(resMedicos.data)
      setQuimicos(resQuimicos.data)
      if (resQuimicos.data.length > 0) {
        setQuimicoGeneracion(resQuimicos.data[0].id)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const fetchResultados = async () => {
    setLoading(true)
    try {
      // Cargamos una cantidad mayor para poder agrupar visitas de forma representativa
      const filters = { page, limit: 150 }
      if (filtroPrueba) filters.prueba_id = filtroPrueba
      if (filtroMedico) filters.medico_id = filtroMedico
      if (filtroFechaDesde) filters.fecha_desde = filtroFechaDesde
      if (filtroFechaHasta) filters.fecha_hasta = filtroFechaHasta
      if (filtroInterpretacion !== 'todos') filters.interpretacion = filtroInterpretacion
      if (filtroPaciente.trim()) filters.search = filtroPaciente.trim()

      const response = await getResultados(filters)
      
      const totalCount = parseInt(response.headers['x-total-count'] || '0', 10)
      setTotalPages(Math.ceil(totalCount / 150) || 1)
      
      let items = response.data
      
      const grouped = groupResultadosIntoVisitas(items)
      setVisitas(grouped)
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar los resultados de laboratorio.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCatalogos()
  }, [])

  useEffect(() => {
    fetchResultados()
  }, [page, filtroPrueba, filtroMedico, filtroFechaDesde, filtroFechaHasta, filtroInterpretacion])

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
    fetchResultados()
  }

  const handleSelectRow = (key) => {
    setSelectedVisitaKeys(prev =>
      prev.includes(key) ? prev.filter(x => x !== key) : [...prev, key]
    )
  }

  const handleSelectAll = () => {
    if (selectedVisitaKeys.length === visitas.length) {
      setSelectedVisitaKeys([])
    } else {
      setSelectedVisitaKeys(visitas.map(v => v.key))
    }
  }

  const handleOpenPreview = async (e, v) => {
    e.stopPropagation()
    setPreviewVisita(v)
    setPreviewTab('clinical')
    setPreviewPdfUrl('')
    setReporteId(null)
    setPreviewModalOpen(true)
    
    setDestinatarioEmail(v.paciente.email || '')
    setDestinatarioWhatsapp(v.paciente.whatsapp || '')
  }

  const handleGenerarPDFParaVisita = async (v) => {
    setReporteGenerando(true)
    setPreviewPdfLoading(true)
    try {
      notify.info('Generando reporte PDF de la visita...')
      const response = await generarReporte({
        paciente_id: v.paciente.id,
        resultado_ids: v.resultadoIds,
        quimico_id: quimicoGeneracion || null
      })
      
      const rep = response.data
      setReporteId(rep.id)
      setActiveReporteId(rep.id)
      notify.success(`Reporte PDF generado. Folio: ${rep.folio}`)
      
      // Descargar el archivo blob con autenticación para previsualizarlo
      const pdfRes = await descargarReporte(rep.id)
      const url = URL.createObjectURL(new Blob([pdfRes.data], { type: 'application/pdf' }))
      setPreviewPdfUrl(url)
      setPreviewTab('pdf')
    } catch (err) {
      console.error(err)
      notify.error('Error al generar el reporte PDF.')
    } finally {
      setReporteGenerando(false)
      setPreviewPdfLoading(false)
    }
  }

  const handleGenerarMasivoVisitas = async () => {
    if (selectedVisitaKeys.length === 0) return
    setLoading(true)
    try {
      notify.info(`Generando reportes para ${selectedVisitaKeys.length} visita(s)...`)
      let exitososCount = 0
      for (const key of selectedVisitaKeys) {
        const v = visitas.find(x => x.key === key)
        if (v) {
          await generarReporte({
            paciente_id: v.paciente.id,
            resultado_ids: v.resultadoIds,
            quimico_id: quimicoGeneracion || null
          })
          exitososCount++
        }
      }
      notify.success(`Se generaron ${exitososCount} reportes PDF con éxito.`)
      setSelectedVisitaKeys([])
      fetchResultados()
    } catch (err) {
      console.error(err)
      notify.error('Ocurrió un error al generar los reportes masivos.')
    } finally {
      setLoading(false)
    }
  }

  const handleEnviarEmail = async (e) => {
    e.preventDefault()
    if (!destinatarioEmail.trim()) {
      notify.error('Por favor, ingresa el correo del destinatario.')
      return
    }

    setEnviando(true)
    try {
      notify.info('Enviando reporte por correo...')
      await enviarEmail({
        reporte_id: activeReporteId || reporteId,
        destinatario_email: destinatarioEmail,
        copia_medico: copiaMedico
      })
      notify.success('El envío por correo ha sido programado exitosamente.')
      setEmailModalOpen(false)
      setWhatsappModalOpen(true)
    } catch (err) {
      console.error(err)
      notify.error('Error al programar el envío del correo.')
    } finally {
      setEnviando(false)
    }
  }

  const handleEnviarWhatsapp = async (e) => {
    e.preventDefault()
    if (!destinatarioWhatsapp.trim()) {
      notify.error('Por favor, ingresa el número de WhatsApp.')
      return
    }

    setEnviando(true)
    try {
      notify.info('Enviando reporte por WhatsApp...')
      await enviarWhatsapp({
        reporte_id: activeReporteId || reporteId,
        destinatario_whatsapp: destinatarioWhatsapp
      })
      notify.success('El envío por WhatsApp ha sido programado exitosamente.')
      setWhatsappModalOpen(false)
    } catch (err) {
      console.error(err)
      notify.error('Error al programar el envío por WhatsApp.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Filters and Search ────────────────────────────────── */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-4">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
              <Search className="w-5 h-5" />
            </span>
            <input
              type="text"
              placeholder="Buscar por paciente (nombre, apellido, identificación)..."
              value={filtroPaciente}
              onChange={(e) => setFiltroPaciente(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500 transition"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-xl shadow-sm active:scale-98 transition"
          >
            Buscar
          </button>
        </form>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-2 border-t border-slate-100">
          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
              Estudio / Prueba
            </label>
            <select
              value={filtroPrueba}
              onChange={(e) => setFiltroPrueba(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
            >
              <option value="">Todos</option>
              {pruebas.map(p => (
                <option key={p.id} value={p.id}>{p.nombre} ({p.codigo})</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
              Médico
            </label>
            <select
              value={filtroMedico}
              onChange={(e) => setFiltroMedico(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
            >
              <option value="">Todos</option>
              {medicos.map(m => (
                <option key={m.id} value={m.id}>{m.nombre} {m.apellido}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
              Interpretación
            </label>
            <select
              value={filtroInterpretacion}
              onChange={(e) => setFiltroInterpretacion(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
            >
              <option value="todos">Todos</option>
              <option value="normal">Normal</option>
              <option value="alto">Alto</option>
              <option value="bajo">Bajo</option>
              <option value="critico">Crítico</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
              Fecha Toma (Desde)
            </label>
            <input
              type="date"
              value={filtroFechaDesde}
              onChange={(e) => setFiltroFechaDesde(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
            />
          </div>
        </div>
      </div>

      {/* ── Action bar ────────────────────────────────────────── */}
      {selectedVisitaKeys.length > 0 && (
        <div className="flex items-center justify-between p-4 bg-teal-50 border border-teal-100 rounded-2xl animate-fade-in">
          <div className="flex items-center gap-2 text-teal-800 text-sm">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>
              Has seleccionado <strong>{selectedVisitaKeys.length}</strong> visita(s) médica(s) de pacientes.
            </span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2">
              <span className="text-xs font-semibold text-teal-800">Firma:</span>
              <select
                value={quimicoGeneracion}
                onChange={(e) => setQuimicoGeneracion(e.target.value)}
                className="px-2 py-1.5 border border-teal-200 rounded-lg text-teal-800 text-xs focus:outline-none focus:border-teal-500 bg-white"
              >
                <option value="">-- Sin Químico --</option>
                {quimicos.map(q => (
                  <option key={q.id} value={q.id}>{q.nombre_completo}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleGenerarMasivoVisitas}
              className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold uppercase tracking-wider rounded-xl shadow-md transition"
            >
              Generar Reportes PDF Masivos
            </button>
          </div>
        </div>
      )}

      {/* ── Table Section ─────────────────────────────────────── */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">
                <th className="pb-3 w-10">
                  <button onClick={handleSelectAll} className="p-1 rounded hover:bg-slate-100 transition">
                    {selectedVisitaKeys.length === visitas.length && visitas.length > 0 ? (
                      <CheckSquare className="w-4 h-4 text-teal-600" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-400" />
                    )}
                  </button>
                </th>
                <th className="pb-3 font-semibold">Paciente</th>
                <th className="pb-3 font-semibold">Fecha Visita</th>
                <th className="pb-3 font-semibold">Estudios Realizados</th>
                <th className="pb-3 font-semibold text-center">Médico Solicitante</th>
                <th className="pb-3 font-semibold text-center">Estatus General</th>
                <th className="pb-3 font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-600">
              {visitas.map((v) => (
                <tr
                  key={v.key}
                  onClick={() => handleSelectRow(v.key)}
                  className={`
                    text-sm hover:bg-slate-50/50 cursor-pointer transition
                    ${selectedVisitaKeys.includes(v.key) ? 'bg-teal-50/20' : ''}
                  `}
                >
                  <td className="py-3.5" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => handleSelectRow(v.key)} className="p-1 rounded hover:bg-slate-100 transition">
                      {selectedVisitaKeys.includes(v.key) ? (
                        <CheckSquare className="w-4 h-4 text-teal-600" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-400" />
                      )}
                    </button>
                  </td>
                  <td className="py-3.5">
                    <div className="font-semibold text-slate-800">{v.paciente.nombre} {v.paciente.apellido} {v.paciente.apellido_materno || ''}</div>
                    <div className="text-[10px] text-slate-400 uppercase font-mono">{v.paciente.identificacion}</div>
                  </td>
                  <td className="py-3.5 text-slate-500 text-xs">
                    {new Date(v.fecha_toma).toLocaleDateString('es-MX', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </td>
                  <td className="py-3.5">
                    <div className="flex flex-wrap gap-1">
                      {v.estudios.map((est, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 text-[10px] font-bold font-mono bg-slate-100 text-slate-600 rounded-md border border-slate-200"
                          title={est.prueba.nombre}
                        >
                          {est.prueba.codigo}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3.5 text-center text-xs">
                    <div className="font-medium text-slate-700">Dr. {v.medico.nombre} {v.medico.apellido || ''}</div>
                    <div className="text-slate-400 uppercase font-mono text-[10px]">Ced: {v.medico.cedula}</div>
                  </td>
                  <td className="py-3.5 text-center">
                    <Badge variant={v.interpretacionMaxima} />
                  </td>
                  <td className="py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={(e) => handleOpenPreview(e, v)}
                      className="p-2 rounded-xl text-slate-500 hover:text-teal-600 hover:bg-slate-50 transition border border-transparent hover:border-slate-100 shadow-sm"
                      title="Ver Detalles y PDF de Visita"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {visitas.length === 0 && !loading && (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-400">
                    No se encontraron visitas registradas con los filtros aplicados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </div>

      {/* ── Preview Visita Modal ───────────────────────────────── */}
      <Modal
        open={previewModalOpen}
        onClose={() => setPreviewModalOpen(false)}
        title="Previsualización de Reporte de Visita"
        size="lg"
      >
        {previewVisita && (
          <div className="space-y-6 text-slate-700">
            {/* Header info */}
            <div className="flex flex-col sm:flex-row justify-between border-b border-slate-100 pb-4 gap-4">
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Paciente</div>
                <div className="text-lg font-bold text-slate-800">
                  {previewVisita.paciente.nombre} {previewVisita.paciente.apellido} {previewVisita.paciente.apellido_materno || ''}
                </div>
                <div className="text-xs font-mono text-slate-500 uppercase">{previewVisita.paciente.identificacion}</div>
                <div className="text-xs text-slate-500 mt-1">
                  Sexo: {previewVisita.paciente.sexo || 'N/A'} | F. Nac: {previewVisita.paciente.fecha_nacimiento ? new Date(previewVisita.paciente.fecha_nacimiento).toLocaleDateString('es-MX') : 'N/A'}
                </div>
              </div>
              <div className="sm:text-right">
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Médico Solicitante</div>
                <div className="text-sm font-semibold text-slate-800">
                  Dr. {previewVisita.medico.nombre} {previewVisita.medico.apellido || ''}
                </div>
                <div className="text-xs text-slate-500">Cédula: {previewVisita.medico.cedula}</div>
                <div className="text-xs text-slate-500 italic mt-0.5">{previewVisita.medico.especialidad || 'General'}</div>
              </div>
            </div>

            {/* Tab Selector */}
            <div className="flex border-b border-slate-200">
              <button
                className={`px-4 py-2 text-sm font-bold border-b-2 transition ${previewTab === 'clinical' ? 'border-teal-500 text-teal-600' : 'border-transparent text-slate-400 hover:text-slate-700'}`}
                onClick={() => setPreviewTab('clinical')}
              >
                Resultados Clínicos ({previewVisita.estudios.length})
              </button>
              <button
                className={`px-4 py-2 text-sm font-bold border-b-2 transition ${previewTab === 'survey' ? 'border-teal-500 text-teal-600' : 'border-transparent text-slate-400 hover:text-slate-700'}`}
                onClick={() => setPreviewTab('survey')}
              >
                Ficha Cuestionario
              </button>
              <button
                className={`px-4 py-2 text-sm font-bold border-b-2 transition flex items-center gap-1.5 ${previewTab === 'pdf' ? 'border-teal-500 text-teal-600' : 'border-transparent text-slate-400 hover:text-slate-700'}`}
                onClick={() => {
                  if (previewPdfUrl) {
                    setPreviewTab('pdf')
                  } else {
                    handleGenerarPDFParaVisita(previewVisita)
                  }
                }}
              >
                {previewPdfLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Reporte PDF Oficial</span>
              </button>
            </div>

            {/* Tab content 1: Clinical values */}
            {previewTab === 'clinical' && (
              <div className="space-y-4">
                <div className="overflow-x-auto border border-slate-100 rounded-xl">
                  <table className="w-full border-collapse text-left text-sm bg-white">
                    <thead>
                      <tr className="bg-slate-50 text-xs font-bold text-slate-400 uppercase border-b border-slate-100">
                        <th className="p-3">Código</th>
                        <th className="p-3">Prueba / Estudio</th>
                        <th className="p-3 text-center">Valor</th>
                        <th className="p-3 text-center">Límites Ref</th>
                        <th className="p-3 text-center">Interpretación</th>
                        <th className="p-3">Observaciones</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-600">
                      {previewVisita.estudios.map((est, i) => (
                        <tr key={i} className="hover:bg-slate-50/50">
                          <td className="p-3 font-mono font-bold text-xs">{est.prueba.codigo}</td>
                          <td className="p-3">
                            <div className="font-semibold text-slate-800">{est.prueba.nombre}</div>
                            <div className="text-[10px] text-slate-400">{est.prueba.categoria}</div>
                          </td>
                          <td className="p-3 text-center font-bold font-mono">
                            {est.valor !== null ? `${est.valor} ${est.prueba.unidad}` : est.valor_texto}
                          </td>
                          <td className="p-3 text-center text-xs text-slate-400">
                            {est.prueba.valor_min !== null && est.prueba.valor_max !== null ? (
                              <span>{est.prueba.valor_min} - {est.prueba.valor_max} {est.prueba.unidad}</span>
                            ) : (
                              <span>N/A</span>
                            )}
                          </td>
                          <td className="p-3 text-center">
                            <Badge variant={est.interpretacion === 'critico_alto' || est.interpretacion === 'critico_bajo' ? 'critico' : est.interpretacion} />
                          </td>
                          <td className="p-3 text-xs italic text-slate-455">{est.observaciones || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-teal-50/50 p-4 rounded-xl border border-teal-100/50">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                    <span className="text-xs text-teal-800 font-medium">
                      ¿Deseas descargar o enviar este reporte?
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-teal-800">Firma:</span>
                      <select
                        value={quimicoGeneracion}
                        onChange={(e) => setQuimicoGeneracion(e.target.value)}
                        className="px-2 py-1 border border-teal-200 rounded-lg text-teal-800 text-xs focus:outline-none focus:border-teal-500 bg-white"
                      >
                        <option value="">-- Sin Químico --</option>
                        {quimicos.map(q => (
                          <option key={q.id} value={q.id}>{q.nombre_completo}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <button
                    onClick={() => handleGenerarPDFParaVisita(previewVisita)}
                    className="px-4 py-1.5 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-lg shadow-sm transition"
                    disabled={reporteGenerando}
                  >
                    {reporteGenerando ? 'Generando PDF...' : 'Generar PDF e Iniciar Envío'}
                  </button>
                </div>
              </div>
            )}

            {/* Tab content 2: Ficha Cuestionario */}
            {previewTab === 'survey' && (
              <div className="space-y-4 text-slate-700 animate-fadeIn">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Datos Clínicos */}
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
                    <h4 className="font-bold text-xs text-slate-400 uppercase tracking-wider">Medidas y Clínica</h4>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-[10px] text-slate-400 block font-bold uppercase">Peso</span>
                        <span className="font-semibold text-slate-800">{previewVisita.paciente.peso ? `${previewVisita.paciente.peso} kg` : 'No registrado'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block font-bold uppercase">Estatura</span>
                        <span className="font-semibold text-slate-800">{previewVisita.paciente.estatura ? `${previewVisita.paciente.estatura} m` : 'No registrado'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block font-bold uppercase">Derechohabiencia</span>
                        <span className="font-semibold text-slate-800">{previewVisita.paciente.derechohabiencia || 'No registrado'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block font-bold uppercase">Suplementos</span>
                        <span className="font-semibold text-slate-800">{previewVisita.paciente.suplemento_detalle || 'Ninguno'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Hábitos de Agua */}
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
                    <h4 className="font-bold text-xs text-slate-400 uppercase tracking-wider font-bold">Hábitos de Consumo</h4>
                    <div className="space-y-3 text-sm">
                      <div>
                        <span className="text-[10px] text-slate-400 block font-bold uppercase">Agua para tomar</span>
                        <span className="font-semibold text-slate-800">{previewVisita.paciente.tipo_agua || 'No registrado'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 block font-bold uppercase">¿Cocina con agua de la llave?</span>
                        <span className="font-semibold text-slate-800">{previewVisita.paciente.cocina_agua_llave || 'No registrado'}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Padecimientos */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-2">
                  <h4 className="font-bold text-xs text-slate-400 uppercase tracking-wider">Padecimientos Clínicos del Paciente</h4>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {previewVisita.paciente.padecimientos ? (
                      previewVisita.paciente.padecimientos.split(',').map((pad, idx) => (
                        <span key={idx} className="px-2.5 py-1 bg-teal-50 text-teal-800 border border-teal-100 rounded-lg text-xs font-semibold">
                          {pad}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-400 italic">Ningún padecimiento reportado por el paciente.</span>
                    )}
                  </div>
                </div>

                {/* Domicilio */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-2">
                  <h4 className="font-bold text-xs text-slate-400 uppercase tracking-wider">Información de Contacto y Domicilio</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-[10px] text-slate-400 block font-bold uppercase">Calle y Colonia</span>
                      <span className="font-semibold text-slate-800">{previewVisita.paciente.domicilio || 'No registrado'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block font-bold uppercase">Código Postal</span>
                      <span className="font-semibold text-slate-800">{previewVisita.paciente.codigo_postal || 'No registrado'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block font-bold uppercase">Municipio</span>
                      <span className="font-semibold text-slate-800">{previewVisita.paciente.municipio_residencia || 'No registrado'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block font-bold uppercase">Estado</span>
                      <span className="font-semibold text-slate-800">{previewVisita.paciente.estado_residencia || 'No registrado'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Tab content 3: PDF preview */}
            {previewTab === 'pdf' && (
              <div className="space-y-4">
                {previewPdfUrl ? (
                  <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-sm bg-slate-100">
                    <iframe
                      src={previewPdfUrl}
                      title="Vista previa del reporte PDF"
                      className="w-full h-[450px] border-none"
                    />
                  </div>
                ) : (
                  <div className="py-20 text-center flex flex-col items-center justify-center space-y-4 border border-dashed border-slate-200 rounded-2xl bg-slate-50">
                    <Loader2 className="w-8 h-8 text-teal-500 animate-spin" />
                    <p className="text-sm font-medium text-slate-500">Cargando previsualización del PDF oficial...</p>
                  </div>
                )}

                {reporteId && (
                  <div className="flex flex-wrap gap-3 justify-center bg-slate-50 p-4 rounded-xl border border-slate-100">
                    <button
                      onClick={() => {
                        setActiveReporteId(reporteId)
                        setEmailModalOpen(true)
                      }}
                      className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold rounded-xl shadow-sm transition flex items-center gap-1.5"
                    >
                      <Mail className="w-3.5 h-3.5" />
                      <span>Enviar por Correo</span>
                    </button>
                    <button
                      onClick={() => {
                        setActiveReporteId(reporteId)
                        setWhatsappModalOpen(true)
                      }}
                      className="px-5 py-2 bg-slate-600 hover:bg-slate-700 text-white text-xs font-bold rounded-xl shadow-sm transition flex items-center gap-1.5"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Enviar por WhatsApp</span>
                    </button>
                    <a
                      href={previewPdfUrl}
                      download={`Reporte_${previewVisita.paciente.nombre}_${previewVisita.fecha_toma}.pdf`}
                      className="px-5 py-2 border border-slate-200 text-slate-600 hover:bg-slate-150 font-bold text-xs rounded-xl transition flex items-center gap-1.5 bg-white"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Descargar PDF</span>
                    </a>
                  </div>
                )}
              </div>
            )}

            {/* Footer Close Button */}
            <div className="flex justify-end pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setPreviewModalOpen(false)}
                className="px-6 py-2 bg-slate-800 hover:bg-slate-900 text-white font-medium rounded-xl shadow-sm transition"
              >
                Cerrar Panel
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Send Email Modal ──────────────────────────────────── */}
      <Modal
        open={emailModalOpen}
        onClose={() => setEmailModalOpen(false)}
        title="Enviar Reporte por Correo"
      >
        <form onSubmit={handleEnviarEmail} className="space-y-4">
          <p className="text-sm text-slate-500">
            El PDF ha sido generado exitosamente. Ingresa el correo electrónico del paciente para enviarlo de inmediato.
          </p>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Correo Electrónico
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Mail className="w-5 h-5" />
              </span>
              <input
                type="email"
                value={destinatarioEmail}
                onChange={(e) => setDestinatarioEmail(e.target.value)}
                placeholder="paciente@ejemplo.com"
                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                required
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="copiaMedico"
              checked={copiaMedico}
              onChange={(e) => setCopiaMedico(e.target.checked)}
              className="w-4 h-4 text-teal-600 border-slate-300 rounded focus:ring-teal-500"
            />
            <label htmlFor="copiaMedico" className="text-xs font-medium text-slate-600">
              Enviar copia al médico solicitante
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => {
                setEmailModalOpen(false)
                setWhatsappModalOpen(true)
              }}
              className="px-4 py-2 border border-slate-200 text-slate-600 font-medium rounded-xl hover:bg-slate-50 transition"
              disabled={enviando}
            >
              Saltar a WhatsApp
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium rounded-xl shadow-sm transition flex items-center gap-2"
              disabled={enviando}
            >
              {enviando ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Mail className="w-4 h-4" />
              )}
              <span>Enviar Correo</span>
            </button>
          </div>
        </form>
      </Modal>

      {/* ── Send WhatsApp Modal ────────────────────────────────── */}
      <Modal
        open={whatsappModalOpen}
        onClose={() => setWhatsappModalOpen(false)}
        title="Enviar Reporte por WhatsApp"
      >
        <form onSubmit={handleEnviarWhatsapp} className="space-y-4">
          <p className="text-sm text-slate-500">
            Ingresa el número de WhatsApp del paciente (con código de país, ej: +521...) para enviar el aviso y el enlace seguro de descarga.
          </p>

          <div>
            <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
              Número de WhatsApp
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Send className="w-5 h-5" />
              </span>
              <input
                type="text"
                value={destinatarioWhatsapp}
                onChange={(e) => setDestinatarioWhatsapp(e.target.value)}
                placeholder="+52 1 55 1234 5678"
                className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                required
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => setWhatsappModalOpen(false)}
              className="px-4 py-2 border border-slate-200 text-slate-650 font-medium rounded-xl hover:bg-slate-50 transition"
              disabled={enviando}
            >
              Cerrar
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium rounded-xl shadow-sm transition flex items-center gap-2"
              disabled={enviando}
            >
              {enviando ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              <span>Enviar WhatsApp</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
