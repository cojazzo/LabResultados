import { useState, useEffect } from 'react'
import { Search, User, ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import api from '../api/client.js'
import Pagination from '../components/Pagination'
import LoadingSkeleton from '../components/LoadingSkeleton'

export default function PerfilesPage() {
  const [pacientes, setPacientes] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  
  // Paginación
  const [currentPage, setCurrentPage] = useState(1)
  const [totalItems, setTotalItems] = useState(0)
  const limit = 20

  useEffect(() => {
    fetchPacientes()
  }, [currentPage])

  const fetchPacientes = async () => {
    try {
      setLoading(true)
      // Usaremos el endpoint actual de pacientes (que debemos asumir que existe o crear)
      // Si no existe, podemos listarlos usando el router existente.
      const res = await api.get(`/pacientes?page=${currentPage}&limit=${limit}`)
      // Asumiendo que retorna { items: [], total: x }
      if (Array.isArray(res.data)) {
        setPacientes(res.data)
        setTotalItems(res.data.length * 2) // mock si no hay count real
      } else {
        setPacientes(res.data.items || [])
        setTotalItems(res.data.total || 0)
      }
    } catch (error) {
      console.error('Error cargando pacientes:', error)
    } finally {
      setLoading(false)
    }
  }

  // Filtrado local simple por nombre/identificacion
  const filteredPacientes = pacientes.filter(p => 
    (p.nombre || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (p.identificacion || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Perfiles de Pacientes</h1>
          <p className="text-slate-500 text-sm">Gestiona el historial y datos de pacientes</p>
        </div>
      </div>

      {/* Barra de búsqueda */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-200">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Buscar por nombre, CURP o folio..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:bg-white transition-colors"
          />
        </div>
      </div>

      {/* Lista de pacientes */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-4">
             <LoadingSkeleton className="h-16 w-full" />
             <LoadingSkeleton className="h-16 w-full" />
             <LoadingSkeleton className="h-16 w-full" />
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredPacientes.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <User className="w-12 h-12 mx-auto text-slate-300 mb-3" />
                <p>No se encontraron pacientes.</p>
              </div>
            ) : (
              filteredPacientes.map((paciente) => (
                <Link 
                  key={paciente.id} 
                  to={`/perfiles/${paciente.id}`}
                  className="flex items-center p-4 hover:bg-slate-50 transition-colors group"
                >
                  <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0 font-bold">
                    {paciente.nombre?.charAt(0) || 'P'}
                  </div>
                  <div className="ml-4 flex-1">
                    <h3 className="font-medium text-slate-800 group-hover:text-emerald-600 transition-colors">
                      {paciente.nombre} {paciente.apellido} {paciente.apellido_materno || ''}
                    </h3>
                    <p className="text-sm text-slate-500 flex gap-2">
                      <span className="font-mono bg-slate-100 px-1.5 rounded">{paciente.identificacion}</span>
                      {paciente.email && <span>• {paciente.email}</span>}
                    </p>
                  </div>
                  <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-emerald-500" />
                </Link>
              ))
            )}
          </div>
        )}
      </div>

      {!loading && totalItems > limit && (
        <Pagination
          currentPage={currentPage}
          totalItems={totalItems}
          itemsPerPage={limit}
          onPageChange={setCurrentPage}
        />
      )}
    </div>
  )
}
