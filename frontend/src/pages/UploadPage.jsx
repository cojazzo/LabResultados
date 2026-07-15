import { useState, useEffect, useRef } from 'react'
import { uploadExcel, getLotes, generarMasivo } from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'
import { Upload, FileSpreadsheet, Loader2, Info, AlertCircle, FileText, Send } from 'lucide-react'
import Badge from '../components/Badge.jsx'
import Modal from '../components/Modal.jsx'
import Pagination from '../components/Pagination.jsx'

export default function UploadPage() {
  const notify = useNotification()
  const fileInputRef = useRef(null)
  
  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [lotes, setLotes] = useState([])
  const [page, setPage] = useState(1)
  const [loadingHistory, setLoadingHistory] = useState(false)
  
  // Detalle de errores de lote
  const [errorModalOpen, setErrorModalOpen] = useState(false)
  const [selectedLote, setSelectedLote] = useState(null)
  
  // Reportes masivos
  const [generatingBatch, setGeneratingBatch] = useState(false)

  const fetchHistory = async () => {
    setLoadingHistory(true)
    try {
      const response = await getLotes(page)
      setLotes(response.data)
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar historial de lotes.')
    } finally {
      setLoadingHistory(false)
    }
  }

  useEffect(() => {
    fetchHistory()
  }, [page])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const files = Array.from(e.dataTransfer.files)
      // Validar extensión
      const validFiles = files.filter(f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))
      if (validFiles.length !== files.length) {
        notify.warning('Solo se permiten archivos Excel (.xlsx, .xls)')
      }
      setSelectedFiles(prev => [...prev, ...validFiles])
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const files = Array.from(e.target.files)
      setSelectedFiles(prev => [...prev, ...files])
    }
  }

  const handleRemoveFile = (idx) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== idx))
  }

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return
    setUploading(true)
    try {
      notify.info('Subiendo y procesando archivos...')
      const response = await uploadExcel(selectedFiles)
      notify.success(response.data.mensaje || 'Archivos procesados correctamente.')
      setSelectedFiles([])
      setPage(1)
      fetchHistory()
    } catch (err) {
      console.error(err)
      notify.error(err.response?.data?.detail || 'Error al procesar el archivo Excel.')
    } finally {
      setUploading(false)
    }
  }

  const handleOpenErrors = (lote) => {
    setSelectedLote(lote)
    setErrorModalOpen(true)
  }

  const handleGenerarMasivo = async (loteId) => {
    setGeneratingBatch(true)
    try {
      notify.info('Generando reportes PDF en lote...')
      const response = await generarMasivo({ lote_id: loteId })
      notify.success(`Generación masiva completada: ${response.data.length} reportes creados.`)
      fetchHistory()
    } catch (err) {
      console.error(err)
      notify.error('Error en generación masiva de reportes.')
    } finally {
      setGeneratingBatch(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* ── Drag & Drop Upload Zone ───────────────────────────── */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 space-y-6">
        <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">
          Cargar Nuevos Resultados (Excel)
        </h3>

        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
          className={`
            border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200
            ${dragActive ? 'border-teal-500 bg-teal-50/50' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'}
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".xlsx, .xls"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-teal-50 flex items-center justify-center text-teal-600">
              <Upload className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700">
                Arrastra archivos Excel aquí o haz clic para seleccionar
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Formatos soportados: .xlsx, .xls (Tamaño máximo: 10MB)
              </p>
            </div>
          </div>
        </div>

        {/* Selected files list */}
        {selectedFiles.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Archivos Seleccionados ({selectedFiles.length})
            </h4>
            <div className="divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden bg-slate-50/30">
              {selectedFiles.map((f, idx) => (
                <div key={idx} className="flex items-center justify-between px-4 py-3 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileSpreadsheet className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <span className="font-medium text-slate-700 truncate">{f.name}</span>
                    <span className="text-xs text-slate-400">({(f.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemoveFile(idx)
                    }}
                    className="text-xs text-red-500 hover:text-red-700 font-medium px-2 py-1 rounded-lg hover:bg-red-50 transition"
                  >
                    Quitar
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="px-6 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-medium rounded-xl shadow-sm hover:shadow active:scale-98 disabled:opacity-50 transition flex items-center gap-2"
              >
                {uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Procesando...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    <span>Cargar e Ingerir</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Upload History ────────────────────────────────────── */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col">
        <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-6">
          Historial de Cargas
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">
                <th className="pb-3 font-semibold">Archivo</th>
                <th className="pb-3 font-semibold">Fecha de Carga</th>
                <th className="pb-3 font-semibold">Estado</th>
                <th className="pb-3 font-semibold">Registros</th>
                <th className="pb-3 font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {lotes.map((l) => (
                <tr key={l.id} className="text-sm text-slate-600 hover:bg-slate-50/50 transition">
                  <td className="py-3.5 font-medium text-slate-800">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
                      <span>{l.nombre}</span>
                    </div>
                  </td>
                  <td className="py-3.5 text-slate-400 text-xs">
                    {new Date(l.fecha_carga).toLocaleString('es-MX')}
                  </td>
                  <td className="py-3.5">
                    <Badge variant={l.estado === 'error_parcial' ? 'parcial' : l.estado}>
                      {l.estado === 'error_parcial' ? 'Parcial' : l.estado}
                    </Badge>
                  </td>
                  <td className="py-3.5 text-xs">
                    <span className="font-bold text-slate-700">{l.registros_exitosos}</span>
                    <span className="text-slate-400"> / {l.total_registros}</span>
                    {l.registros_error > 0 && (
                      <span className="ml-2 text-red-500 font-bold">({l.registros_error} errores)</span>
                    )}
                  </td>
                  <td className="py-3.5 text-right space-x-2">
                    {l.registros_error > 0 && (
                      <button
                        onClick={() => handleOpenErrors(l)}
                        className="px-3 py-1 text-xs border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition"
                      >
                        Ver Errores
                      </button>
                    )}
                    {l.registros_exitosos > 0 && (
                      <button
                        onClick={() => handleGenerarMasivo(l.id)}
                        disabled={generatingBatch}
                        className="px-3 py-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition inline-flex items-center gap-1"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Generar PDFs</span>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {lotes.length === 0 && !loadingHistory && (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-slate-400">
                    No hay registros de cargas anteriores.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Errors Modal ──────────────────────────────────────── */}
      <Modal
        open={errorModalOpen}
        onClose={() => setErrorModalOpen(false)}
        title={`Errores de carga - ${selectedLote?.nombre}`}
        size="lg"
      >
        <div className="space-y-4">
          <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-100 rounded-xl text-red-700 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>
              Se detectaron <strong>{selectedLote?.registros_error}</strong> registros con errores en este lote. Corrige estos errores en tu Excel y vuelve a subirlo.
            </span>
          </div>

          <div className="border border-slate-100 rounded-xl overflow-hidden">
            <table className="w-full border-collapse text-sm">
              <thead className="bg-slate-50 border-b border-slate-100 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-2">Fila</th>
                  <th className="px-4 py-2">Columna</th>
                  <th className="px-4 py-2">Error</th>
                  <th className="px-4 py-2">Valor Detectado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {selectedLote?.log_errores?.map((err, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/50">
                    <td className="px-4 py-2.5 font-bold text-slate-700">{err.fila}</td>
                    <td className="px-4 py-2.5 font-medium text-slate-600">{err.columna}</td>
                    <td className="px-4 py-2.5 text-red-600">{err.error}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-500 bg-slate-50/30">{err.valor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Modal>
    </div>
  )
}
