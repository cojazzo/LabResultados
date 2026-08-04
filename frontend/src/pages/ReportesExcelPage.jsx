import { useState, useEffect } from 'react'
import {
  FileDown,
  CalendarRange,
  AlertCircle,
  CheckCircle2,
  Loader2,
  TableProperties,
  FlaskConical,
  ClipboardCheck,
  ChevronDown,
  ChevronUp,
  Download,
} from 'lucide-react'
import { exportarReporteExcel, getPruebas, descargarTemplateExcel } from '../api/client.js'

// Columnas de tamizaje disponibles (mismo orden que el backend)
const TAMIZAJE_COLS = [
  'CURP',
  'Nombre',
  'Apellido Paterno',
  'Apellido Materno',
  'Sexo',
  'Fecha Nacimiento',
  'Peso (kg)',
  'Estatura (cm)',
  'IMC',
  'Derechohabiencia',
  'Padecimientos',
  'Tipo de Agua',
  'Cocina con Agua de Llave',
]

// ── Sub-componente: CheckboxPill ─────────────────────────────────────────────
function CheckboxPill({ label, checked, onChange, colorClass = 'slate' }) {
  const activeStyles = {
    slate: 'bg-slate-700 text-white border-slate-700',
    emerald: 'bg-emerald-600 text-white border-emerald-600',
  }
  const inactiveStyles = 'bg-white text-slate-500 border-slate-200 hover:border-slate-300 hover:text-slate-700'

  return (
    <button
      type="button"
      onClick={onChange}
      className={`
        inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium
        transition-all duration-150 select-none
        ${checked ? activeStyles[colorClass] : inactiveStyles}
      `}
    >
      <span
        className={`
          w-3.5 h-3.5 rounded-sm border flex items-center justify-center flex-shrink-0
          ${checked
            ? 'bg-white/30 border-white/50'
            : 'border-slate-300 bg-white'}
        `}
      >
        {checked && (
          <svg className="w-2.5 h-2.5" viewBox="0 0 10 10" fill="none">
            <path d="M1.5 5L4 7.5L8.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      {label}
    </button>
  )
}

// ── Sub-componente: SectionCard ──────────────────────────────────────────────
function SectionCard({ icon: Icon, title, badge, children, colorClass = 'slate', defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)

  const badgeColors = {
    slate: 'bg-slate-100 text-slate-600',
    emerald: 'bg-emerald-100 text-emerald-700',
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-6 py-4 border-b border-slate-100 bg-slate-50/60 hover:bg-slate-100/60 transition-colors text-left"
      >
        <Icon className="w-5 h-5 text-slate-400 flex-shrink-0" />
        <span className="font-semibold text-slate-700 text-sm">{title}</span>
        {badge !== undefined && (
          <span className={`ml-1 px-2 py-0.5 rounded-full text-xs font-semibold ${badgeColors[colorClass]}`}>
            {badge}
          </span>
        )}
        <span className="ml-auto text-slate-400">
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </span>
      </button>
      {open && <div className="p-6">{children}</div>}
    </div>
  )
}

// ── Página principal ─────────────────────────────────────────────────────────
export default function ReportesExcelPage() {
  const [fechaInicio, setFechaInicio] = useState('')
  const [fechaFin, setFechaFin] = useState('')

  // Selección de columnas de tamizaje (todas activas por defecto)
  const [selectedTamizaje, setSelectedTamizaje] = useState(new Set(TAMIZAJE_COLS))

  // Pruebas de laboratorio (cargadas desde el catálogo)
  const [pruebas, setPruebas] = useState([])
  const [loadingPruebas, setLoadingPruebas] = useState(true)
  const [selectedPruebas, setSelectedPruebas] = useState(new Set()) // IDs

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  const [loadingTemplate, setLoadingTemplate] = useState(false)

  // Cargar catálogo de pruebas al montar
  useEffect(() => {
    const fetchPruebas = async () => {
      try {
        const res = await getPruebas()
        const activas = (res.data || []).filter(p => p.activa !== false)
        setPruebas(activas)
        setSelectedPruebas(new Set(activas.map(p => p.id)))
      } catch {
        // Si falla, no bloqueamos la exportación — simplemente no filtramos por prueba
      } finally {
        setLoadingPruebas(false)
      }
    }
    fetchPruebas()
  }, [])

  // ── Helpers de selección ──────────────────────────────────────────
  const toggleTamizaje = (col) => {
    setSelectedTamizaje(prev => {
      const next = new Set(prev)
      next.has(col) ? next.delete(col) : next.add(col)
      return next
    })
  }

  const togglePrueba = (id) => {
    setSelectedPruebas(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const selectAllTamizaje = () => setSelectedTamizaje(new Set(TAMIZAJE_COLS))
  const clearAllTamizaje = () => setSelectedTamizaje(new Set())

  const selectAllPruebas = () => setSelectedPruebas(new Set(pruebas.map(p => p.id)))
  const clearAllPruebas = () => setSelectedPruebas(new Set())

  // ── Exportar ──────────────────────────────────────────────────────
  const handleExport = async () => {
    if (fechaInicio && fechaFin && fechaInicio > fechaFin) {
      setError('La fecha de inicio no puede ser posterior a la fecha de fin.')
      return
    }
    if (selectedTamizaje.size === 0 && selectedPruebas.size === 0) {
      setError('Selecciona al menos una columna o prueba para exportar.')
      return
    }

    setError(null)
    setSuccess(null)
    setLoading(true)

    try {
      // Si todas las pruebas están seleccionadas, no enviamos filtro (más eficiente)
      const allPruebasSelected = pruebas.length > 0 && selectedPruebas.size === pruebas.length
      const pruebaIdsParam = allPruebasSelected ? [] : [...selectedPruebas]

      // Si todos los campos tamizaje están seleccionados, tampoco enviamos filtro
      const allTamizajeSelected = selectedTamizaje.size === TAMIZAJE_COLS.length
      const camposParam = allTamizajeSelected
        ? []
        : TAMIZAJE_COLS.filter(c => selectedTamizaje.has(c))

      const res = await exportarReporteExcel(
        fechaInicio || null,
        fechaFin || null,
        camposParam,
        pruebaIdsParam,
      )

      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : 'Reporte.xlsx'

      const url = URL.createObjectURL(new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)

      setSuccess(`Archivo "${filename}" descargado correctamente.`)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(detail || 'Error al generar el reporte. Intenta nuevamente.')
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setFechaInicio('')
    setFechaFin('')
    setError(null)
    setSuccess(null)
  }

  const totalSeleccionado = selectedTamizaje.size + selectedPruebas.size

  return (
    <div className="max-w-3xl mx-auto space-y-6">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-600 flex-shrink-0">
          <TableProperties className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Reportes Excel</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Selecciona las columnas y genera un Excel personalizado.
          </p>
        </div>
      </div>

      {/* ── Filtro de fechas ─────────────────────────────────────────── */}
      <SectionCard icon={CalendarRange} title="Rango de fechas" defaultOpen={true}>
        <div className="space-y-4">
          <p className="text-xs text-slate-400">Opcional — sin fechas se exportan todos los registros</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-600" htmlFor="fecha-inicio">
                Fecha de inicio
              </label>
              <input
                id="fecha-inicio"
                type="date"
                value={fechaInicio}
                onChange={(e) => setFechaInicio(e.target.value)}
                className="
                  w-full px-3 py-2.5 rounded-xl border border-slate-200
                  text-slate-800 text-sm bg-white
                  focus:outline-none focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400
                  transition-all duration-150
                "
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-600" htmlFor="fecha-fin">
                Fecha de fin
              </label>
              <input
                id="fecha-fin"
                type="date"
                value={fechaFin}
                onChange={(e) => setFechaFin(e.target.value)}
                className="
                  w-full px-3 py-2.5 rounded-xl border border-slate-200
                  text-slate-800 text-sm bg-white
                  focus:outline-none focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400
                  transition-all duration-150
                "
              />
            </div>
          </div>
          {(fechaInicio || fechaFin) && (
            <button
              type="button"
              onClick={handleClear}
              className="text-xs text-slate-400 hover:text-slate-600 underline transition-colors"
            >
              Limpiar fechas
            </button>
          )}
        </div>
      </SectionCard>

      {/* ── Selector columnas de tamizaje ────────────────────────────── */}
      <SectionCard
        icon={ClipboardCheck}
        title="Datos de tamizaje"
        badge={`${selectedTamizaje.size} / ${TAMIZAJE_COLS.length}`}
        colorClass="slate"
      >
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={selectAllTamizaje}
              className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
            >
              Seleccionar todas
            </button>
            <span className="text-slate-200">|</span>
            <button
              type="button"
              onClick={clearAllTamizaje}
              className="text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors"
            >
              Limpiar
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {TAMIZAJE_COLS.map((col) => (
              <CheckboxPill
                key={col}
                label={col}
                checked={selectedTamizaje.has(col)}
                onChange={() => toggleTamizaje(col)}
                colorClass="slate"
              />
            ))}
          </div>
        </div>
      </SectionCard>

      {/* ── Selector pruebas de laboratorio ─────────────────────────── */}
      <SectionCard
        icon={FlaskConical}
        title="Pruebas de laboratorio"
        badge={`${selectedPruebas.size} / ${pruebas.length}`}
        colorClass="emerald"
      >
        {loadingPruebas ? (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            Cargando catálogo…
          </div>
        ) : pruebas.length === 0 ? (
          <p className="text-sm text-slate-400">No hay pruebas activas en el catálogo.</p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={selectAllPruebas}
                className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
              >
                Seleccionar todas
              </button>
              <span className="text-slate-200">|</span>
              <button
                type="button"
                onClick={clearAllPruebas}
                className="text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors"
              >
                Limpiar
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {pruebas.map((prueba) => (
                <CheckboxPill
                  key={prueba.id}
                  label={`${prueba.nombre} (${prueba.unidad})`}
                  checked={selectedPruebas.has(prueba.id)}
                  onChange={() => togglePrueba(prueba.id)}
                  colorClass="emerald"
                />
              ))}
            </div>
          </div>
        )}
      </SectionCard>

      {/* ── Alertas y botón de exportar ─────────────────────────────── */}
      <div className="space-y-3">
        {error && (
          <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm">
            <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{success}</span>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            id="btn-exportar-excel"
            type="button"
            onClick={handleExport}
            disabled={loading || totalSeleccionado === 0}
            className="
              flex items-center gap-2 px-6 py-3 rounded-xl
              bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800
              text-white text-sm font-semibold
              shadow-sm hover:shadow-md
              transition-all duration-200
              disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
            "
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generando…
              </>
            ) : (
              <>
                <FileDown className="w-4 h-4" />
                Generar y Descargar Excel
              </>
            )}
          </button>

          {/* Botón de template */}
          <button
            id="btn-descargar-template"
            type="button"
            onClick={async () => {
              setLoadingTemplate(true)
              try {
                const res = await descargarTemplateExcel()
                const url = URL.createObjectURL(new Blob([res.data], {
                  type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                }))
                const a = document.createElement('a')
                a.href = url
                a.download = 'Template_Laboratorio.xlsx'
                document.body.appendChild(a)
                a.click()
                a.remove()
                URL.revokeObjectURL(url)
              } catch {
                // silencioso
              } finally {
                setLoadingTemplate(false)
              }
            }}
            disabled={loadingTemplate}
            className="
              flex items-center gap-2 px-4 py-3 rounded-xl
              border border-slate-200 bg-white hover:bg-slate-50
              text-slate-600 text-sm font-medium
              transition-all duration-200
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            {loadingTemplate ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Descargar Template
          </button>

          {!loading && (
            <span className="text-xs text-slate-400">
              {totalSeleccionado === 0
                ? 'Selecciona al menos un campo'
                : `${selectedTamizaje.size} campo${selectedTamizaje.size !== 1 ? 's' : ''} de tamizaje + ${selectedPruebas.size} prueba${selectedPruebas.size !== 1 ? 's' : ''}`
              }
            </span>
          )}
        </div>
      </div>

    </div>
  )
}
