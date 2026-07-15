import { useState, useEffect } from 'react'
import { getPruebas, createPrueba, updatePrueba } from '../api/client.js'
import { useNotification } from '../context/NotificationContext.jsx'
import { BookOpen, Plus, Edit2, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'
import Badge from '../components/Badge.jsx'
import Modal from '../components/Modal.jsx'

export default function CatalogoPage() {
  const notify = useNotification()
  const [pruebas, setPruebas] = useState([])
  const [loading, setLoading] = useState(false)
  const [filtroCategoria, setFiltroCategoria] = useState('todos')

  // Modales
  const [modalOpen, setModalOpen] = useState(false)
  const [editingPrueba, setEditingPrueba] = useState(null)
  
  // Form fields
  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [categoria, setCategoria] = useState('')
  const [unidad, setUnidad] = useState('')
  const [valorMin, setValorMin] = useState('')
  const [valorMax, setValorMax] = useState('')
  const [valorCriticoMin, setValorCriticoMin] = useState('')
  const [valorCriticoMax, setValorCriticoMax] = useState('')
  const [metodo, setMetodo] = useState('')
  const [activa, setActiva] = useState(true)
  const [saving, setSaving] = useState(false)

  const fetchPruebas = async () => {
    setLoading(true)
    try {
      const response = await getPruebas()
      setPruebas(response.data)
    } catch (err) {
      console.error(err)
      notify.error('Error al cargar catálogo de pruebas.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPruebas()
  }, [])

  const handleOpenCreate = () => {
    setEditingPrueba(null)
    setCodigo('')
    setNombre('')
    setCategoria('')
    setUnidad('')
    setValorMin('')
    setValorMax('')
    setValorCriticoMin('')
    setValorCriticoMax('')
    setMetodo('')
    setActiva(true)
    setModalOpen(true)
  }

  const handleOpenEdit = (p) => {
    setEditingPrueba(p)
    setCodigo(p.codigo)
    setNombre(p.nombre)
    setCategoria(p.categoria)
    setUnidad(p.unidad)
    setValorMin(p.valor_min !== null ? p.valor_min.toString() : '')
    setValorMax(p.valor_max !== null ? p.valor_max.toString() : '')
    setValorCriticoMin(p.valor_critico_min !== null ? p.valor_critico_min.toString() : '')
    setValorCriticoMax(p.valor_critico_max !== null ? p.valor_critico_max.toString() : '')
    setMetodo(p.metodo || '')
    setActiva(p.activa)
    setModalOpen(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!codigo.trim() || !nombre.trim() || !categoria.trim() || !unidad.trim()) {
      notify.error('Por favor, completa los campos requeridos.')
      return
    }

    const payload = {
      codigo: codigo.trim().toUpperCase(),
      nombre: nombre.trim(),
      categoria: categoria.trim(),
      unidad: unidad.trim(),
      valor_min: valorMin !== '' ? parseFloat(valorMin) : null,
      valor_max: valorMax !== '' ? parseFloat(valorMax) : null,
      valor_critico_min: valorCriticoMin !== '' ? parseFloat(valorCriticoMin) : null,
      valor_critico_max: valorCriticoMax !== '' ? parseFloat(valorCriticoMax) : null,
      metodo: metodo.trim() || null,
      activa
    }

    setSaving(true)
    try {
      if (editingPrueba) {
        await updatePrueba(editingPrueba.id, payload)
        notify.success('Prueba actualizada correctamente.')
      } else {
        await createPrueba(payload)
        notify.success('Prueba creada y agregada al catálogo.')
      }
      setModalOpen(false)
      fetchPruebas()
    } catch (err) {
      console.error(err)
      notify.error(err.response?.data?.detail || 'Error al guardar los datos de la prueba.')
    } finally {
      setSaving(false)
    }
  }

  const uniqueCategories = Array.from(new Set(pruebas.map(p => p.categoria)))
  const filteredPruebas = filtroCategoria === 'todos'
    ? pruebas
    : pruebas.filter(p => p.categoria === filtroCategoria)

  return (
    <div className="space-y-6">
      {/* ── Header actions ────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-3">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Filtrar Categoría:
          </label>
          <select
            value={filtroCategoria}
            onChange={(e) => setFiltroCategoria(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-xl text-slate-700 focus:outline-none focus:border-teal-500 transition"
          >
            <option value="todos">Todas</option>
            {uniqueCategories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        <button
          onClick={handleOpenCreate}
          className="px-5 py-2 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold uppercase tracking-wider rounded-xl shadow-sm transition flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          <span>Agregar Estudio</span>
        </button>
      </div>

      {/* ── Table Section ─────────────────────────────────────── */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">
                <th className="pb-3 font-semibold">Código</th>
                <th className="pb-3 font-semibold">Estudio / Prueba</th>
                <th className="pb-3 font-semibold">Categoría</th>
                <th className="pb-3 font-semibold">Unidad</th>
                <th className="pb-3 font-semibold">Rango Ref.</th>
                <th className="pb-3 font-semibold">Límites Críticos</th>
                <th className="pb-3 font-semibold">Método</th>
                <th className="pb-3 font-semibold">Estado</th>
                <th className="pb-3 font-semibold text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredPruebas.map((p) => (
                <tr key={p.id} className="text-sm text-slate-600 hover:bg-slate-50/50 transition">
                  <td className="py-3.5 font-bold font-mono text-slate-800">{p.codigo}</td>
                  <td className="py-3.5 font-semibold text-slate-700">{p.nombre}</td>
                  <td className="py-3.5 text-xs font-medium text-slate-500">{p.categoria}</td>
                  <td className="py-3.5 font-mono text-xs">{p.unidad}</td>
                  <td className="py-3.5 text-xs text-slate-400 font-mono">
                    {p.valor_min !== null && p.valor_max !== null ? (
                      <span>{p.valor_min} - {p.valor_max}</span>
                    ) : p.valor_max !== null ? (
                      <span>&lt; {p.valor_max}</span>
                    ) : p.valor_min !== null ? (
                      <span>&gt; {p.valor_min}</span>
                    ) : (
                      <span>N/A</span>
                    )}
                  </td>
                  <td className="py-3.5 text-xs font-mono text-red-500">
                    {p.valor_critico_min !== null && (
                      <div className="text-[10px]">Min: &lt;{p.valor_critico_min}</div>
                    )}
                    {p.valor_critico_max !== null && (
                      <div className="text-[10px]">Max: &gt;{p.valor_critico_max}</div>
                    )}
                    {p.valor_critico_min === null && p.valor_critico_max === null && (
                      <span className="text-slate-300">-</span>
                    )}
                  </td>
                  <td className="py-3.5 text-xs italic text-slate-400">{p.metodo || 'Estándar'}</td>
                  <td className="py-3.5">
                    <Badge variant={p.activa ? 'activa' : 'inactiva'}>
                      {p.activa ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="py-3.5 text-right">
                    <button
                      onClick={() => handleOpenEdit(p)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-teal-600 hover:bg-slate-50 transition"
                      title="Editar estudio"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {filteredPruebas.length === 0 && !loading && (
                <tr>
                  <td colSpan="9" className="py-12 text-center text-slate-400">
                    No se encontraron estudios en esta categoría.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Create / Edit Modal ────────────────────────────────── */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingPrueba ? `Editar Estudio - ${editingPrueba.nombre}` : 'Agregar Nuevo Estudio'}
        size="lg"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Código del Estudio *
              </label>
              <input
                type="text"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                placeholder="Ej: GLU, COL-T"
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                required
                disabled={!!editingPrueba}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Nombre del Estudio *
              </label>
              <input
                type="text"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Ej: Glucosa en Ayunas"
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Categoría / Sección *
              </label>
              <input
                type="text"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                placeholder="Ej: Química Sanguínea"
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Unidad de Medida *
              </label>
              <input
                type="text"
                value={unidad}
                onChange={(e) => setUnidad(e.target.value)}
                placeholder="Ej: mg/dL, g/dL"
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                required
              />
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">Rangos de Referencia</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Valor Mínimo Normal</label>
                <input
                  type="number"
                  step="any"
                  value={valorMin}
                  onChange={(e) => setValorMin(e.target.value)}
                  placeholder="0.0"
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-500 mb-1">Valor Máximo Normal</label>
                <input
                  type="number"
                  step="any"
                  value={valorMax}
                  onChange={(e) => setValorMax(e.target.value)}
                  placeholder="200.0"
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                />
              </div>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">Valores Críticos (Pánico)</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Crítico Mínimo (Por debajo)</label>
                <input
                  type="number"
                  step="any"
                  value={valorCriticoMin}
                  onChange={(e) => setValorCriticoMin(e.target.value)}
                  placeholder="40.0"
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-500 mb-1">Crítico Máximo (Por encima)</label>
                <input
                  type="number"
                  step="any"
                  value={valorCriticoMax}
                  onChange={(e) => setValorCriticoMax(e.target.value)}
                  placeholder="400.0"
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-slate-100 pt-4">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                Método Analítico
              </label>
              <input
                type="text"
                value={metodo}
                onChange={(e) => setMetodo(e.target.value)}
                placeholder="Ej: Espectrofotometría"
                className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:border-teal-500 transition"
              />
            </div>

            <div className="flex items-end pb-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={activa}
                  onChange={(e) => setActiva(e.target.checked)}
                  className="w-4 h-4 text-teal-600 border-slate-300 rounded focus:ring-teal-500"
                />
                <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                  Prueba Activa
                </span>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-4 py-2 border border-slate-200 text-slate-600 font-medium rounded-xl hover:bg-slate-50 transition"
              disabled={saving}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white font-medium rounded-xl shadow-sm transition flex items-center gap-2"
              disabled={saving}
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <BookOpen className="w-4 h-4" />
              )}
              <span>Guardar</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
