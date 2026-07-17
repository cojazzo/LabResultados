/**
 * MapaPacientes.jsx
 *
 * Mapa interactivo que muestra la distribución geográfica de los pacientes
 * del laboratorio en Aguascalientes, México.
 *
 * Tecnología: react-leaflet + OpenStreetMap (sin clave de API)
 * Clustering: react-leaflet-cluster (agrupa marcadores cuando hay zoom out)
 */

import { useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'leaflet/dist/leaflet.css'

// ── Constantes geográficas ─────────────────────────────────────────────────
const AGUASCALIENTES_CENTER = [21.8853, -102.2916]
const DEFAULT_ZOOM = 12

/**
 * Elige el color del marcador según la cantidad de pacientes en el cluster.
 *   1-2   → teal    (verde menta del sistema)
 *   3-5   → ámbar
 *   6-10  → naranja
 *   >10   → rojo
 */
function getMarkerColor(total) {
  if (total >= 10) return '#ef4444'
  if (total >= 6)  return '#f97316'
  if (total >= 3)  return '#f59e0b'
  return '#0d9488'
}

function getMarkerRadius(total) {
  if (total >= 10) return 18
  if (total >= 6)  return 14
  if (total >= 3)  return 11
  return 8
}

// ── Componente principal ───────────────────────────────────────────────────
export default function MapaPacientes({ puntos = [], loading = false }) {
  // Fijar el ícono de Leaflet (bug conocido con bundlers)
  useEffect(() => {
    // Leaflet busca los íconos en una ruta relativa que bundlers rompen.
    // Con react-leaflet-cluster usamos CircleMarker, así que esto no aplica,
    // pero lo dejamos como salvaguarda.
  }, [])

  const totalPacientes = puntos.reduce((acc, p) => acc + p.total, 0)

  return (
    <div className="relative w-full h-full">
      {/* ── Header interno del mapa ────────────────────────────────────── */}
      <div className="absolute top-3 left-3 z-[1000] flex items-center gap-2">
        <div className="bg-white/90 backdrop-blur-sm border border-slate-200 rounded-xl px-3 py-1.5 shadow-sm flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
          <span className="text-xs font-semibold text-slate-700">
            {loading
              ? 'Cargando mapa…'
              : `${totalPacientes} paciente${totalPacientes !== 1 ? 's' : ''} en ${puntos.length} zona${puntos.length !== 1 ? 's' : ''}`
            }
          </span>
        </div>
      </div>

      {/* ── Leyenda de colores ─────────────────────────────────────────── */}
      <div className="absolute bottom-8 right-3 z-[1000] bg-white/90 backdrop-blur-sm border border-slate-200 rounded-xl px-3 py-2 shadow-sm space-y-1">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Densidad</p>
        {[
          { color: '#0d9488', label: '1 – 2 pac.' },
          { color: '#f59e0b', label: '3 – 5 pac.' },
          { color: '#f97316', label: '6 – 10 pac.' },
          { color: '#ef4444', label: '> 10 pac.' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            <span className="text-[10px] text-slate-600">{label}</span>
          </div>
        ))}
      </div>

      {/* ── Mapa Leaflet ───────────────────────────────────────────────── */}
      {!loading && (
        <MapContainer
          center={AGUASCALIENTES_CENTER}
          zoom={DEFAULT_ZOOM}
          style={{ width: '100%', height: '100%', borderRadius: '0 0 1rem 1rem' }}
          scrollWheelZoom={true}
          className="z-0"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MarkerClusterGroup chunkedLoading>
            {puntos.map((punto, idx) => (
              <CircleMarker
                key={`punto-${idx}-${punto.lat}-${punto.lon}`}
                center={[punto.lat, punto.lon]}
                radius={getMarkerRadius(punto.total)}
                pathOptions={{
                  color: getMarkerColor(punto.total),
                  fillColor: getMarkerColor(punto.total),
                  fillOpacity: 0.75,
                  weight: 2,
                }}
              >
                <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
                  <div className="text-xs">
                    {punto.colonia && (
                      <div className="font-semibold text-slate-700 mb-0.5">{punto.colonia}</div>
                    )}
                    <div className="text-slate-500">
                      {punto.total} paciente{punto.total !== 1 ? 's' : ''}
                    </div>
                  </div>
                </Tooltip>
              </CircleMarker>
            ))}
          </MarkerClusterGroup>
        </MapContainer>
      )}

      {/* ── Estado vacío ───────────────────────────────────────────────── */}
      {!loading && puntos.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center z-[999] pointer-events-none">
          <div className="bg-white/95 backdrop-blur-sm rounded-2xl border border-slate-200 px-6 py-4 text-center shadow-lg">
            <p className="text-sm font-semibold text-slate-700 mb-1">Sin pacientes geocodificados</p>
            <p className="text-xs text-slate-400">
              Usa el botón <span className="font-semibold text-teal-600">Geocodificar</span> para ubicar a los pacientes en el mapa.
            </p>
          </div>
        </div>
      )}

      {/* ── Overlay de carga ───────────────────────────────────────────── */}
      {loading && (
        <div className="absolute inset-0 bg-slate-50/80 backdrop-blur-sm flex items-center justify-center rounded-b-2xl z-[999]">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-3 border-teal-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs font-medium text-slate-500">Cargando mapa…</p>
          </div>
        </div>
      )}
    </div>
  )
}
