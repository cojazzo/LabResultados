import React, { useMemo, useState } from 'react'
import { MapContainer, TileLayer, Polygon, Tooltip, useMap } from 'react-leaflet'
import { hexbin } from 'd3-hexbin'
import 'leaflet/dist/leaflet.css'

const AGUASCALIENTES_CENTER = [21.8853, -102.2916]
const DEFAULT_ZOOM = 12

// Component to handle auto-centering on load
function AutoCenterMap({ center, zoom }) {
  const map = useMap()
  React.useEffect(() => {
    map.setView(center, zoom)
  }, [center, zoom, map])
  return null
}

export default function MapaHexbin({ 
  data = { tamizados: [], positivos: [] }, 
  loading = false 
}) {
  const [activeLayer, setActiveLayer] = useState('tamizados') // 'tamizados' or 'positivos'

  // The radius in degrees (~1.5 km depending on latitude)
  const RADIUS_DEG = 0.015

  // Memoize the hexbin calculation
  const { bins, maxCount } = useMemo(() => {
    const points = activeLayer === 'tamizados' ? data.tamizados : data.positivos
    
    if (!points || points.length === 0) {
      return { bins: [], maxCount: 0 }
    }

    const hex = hexbin()
      .x(d => d.lon)
      .y(d => d.lat)
      .radius(RADIUS_DEG)

    const calculatedBins = hex(points)
    
    const max = Math.max(...calculatedBins.map(b => b.length), 1)
    
    return { bins: calculatedBins, maxCount: max }
  }, [data, activeLayer])

  // Helper to get 6 vertices of a hexagon given its center and radius
  const getHexagonPolygon = (cx, cy, r) => {
    const points = []
    // d3-hexbin uses pointy-topped hexagons
    for (let i = 0; i < 6; i++) {
      const angle = (i * Math.PI) / 3
      // Leaflet uses [lat, lon] (y, x)
      const px = cx + r * Math.sin(angle)
      const py = cy - r * Math.cos(angle)
      points.push([py, px])
    }
    return points
  }

  // Get color based on density (relative to maxCount)
  const getColor = (count) => {
    const ratio = count / (maxCount || 1)
    
    if (activeLayer === 'tamizados') {
      // Teal gradient
      if (ratio > 0.75) return '#0f766e' // teal-700
      if (ratio > 0.5) return '#0d9488' // teal-600
      if (ratio > 0.25) return '#14b8a6' // teal-500
      return '#5eead4' // teal-300
    } else {
      // Red gradient
      if (ratio > 0.75) return '#b91c1c' // red-700
      if (ratio > 0.5) return '#dc2626' // red-600
      if (ratio > 0.25) return '#ef4444' // red-500
      return '#fca5a5' // red-300
    }
  }

  const totalPoints = activeLayer === 'tamizados' 
    ? (data.tamizados?.length || 0) 
    : (data.positivos?.length || 0)

  return (
    <div className="relative w-full h-full flex flex-col">
      {/* ── Top Controls ───────────────────────────────────────────────── */}
      <div className="absolute top-3 left-3 z-[1000] flex items-center gap-2">
        <div className="bg-white/95 backdrop-blur-sm border border-slate-200 rounded-xl p-1 shadow-sm flex items-center">
          <button
            onClick={() => setActiveLayer('tamizados')}
            className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition ${
              activeLayer === 'tamizados' 
                ? 'bg-teal-50 text-teal-700' 
                : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            Tamizados
          </button>
          <button
            onClick={() => setActiveLayer('positivos')}
            className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
              activeLayer === 'positivos' 
                ? 'bg-red-50 text-red-700' 
                : 'text-slate-500 hover:bg-slate-50'
            }`}
          >
            Positivos (Riesgo Renal)
          </button>
        </div>
      </div>

      <div className="absolute top-3 right-3 z-[1000]">
        <div className="bg-white/90 backdrop-blur-sm border border-slate-200 rounded-xl px-3 py-1.5 shadow-sm">
          <span className="text-xs font-semibold text-slate-700">
            {totalPoints} paciente{totalPoints !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* ── Map ────────────────────────────────────────────────────────── */}
      <div className="flex-1 bg-slate-50 relative z-0">
        {!loading && (
          <MapContainer
            center={AGUASCALIENTES_CENTER}
            zoom={DEFAULT_ZOOM}
            style={{ width: '100%', height: '100%', borderRadius: '0 0 1rem 1rem' }}
            scrollWheelZoom={true}
          >
            <AutoCenterMap center={AGUASCALIENTES_CENTER} zoom={DEFAULT_ZOOM} />
            
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              opacity={0.6} /* Dim base map slightly to make hexbins pop */
            />

            {bins.map((bin, idx) => {
              const count = bin.length
              const color = getColor(count)
              const polygon = getHexagonPolygon(bin.x, bin.y, RADIUS_DEG)
              
              return (
                <Polygon
                  key={`hex-${idx}`}
                  positions={polygon}
                  pathOptions={{
                    fillColor: color,
                    fillOpacity: 0.7,
                    color: 'white', // border color
                    weight: 1,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -10]} opacity={0.95}>
                    <div className="text-center px-1">
                      <div className="font-bold text-slate-700">
                        {count} paciente{count !== 1 ? 's' : ''}
                      </div>
                      <div className="text-[10px] text-slate-500 uppercase mt-0.5">
                        En esta zona
                      </div>
                    </div>
                  </Tooltip>
                </Polygon>
              )
            })}
          </MapContainer>
        )}

        {/* ── Empty State ──────────────────────────────────────────────── */}
        {!loading && totalPoints === 0 && (
          <div className="absolute inset-0 flex items-center justify-center z-[999] pointer-events-none">
            <div className="bg-white/95 backdrop-blur-sm rounded-2xl border border-slate-200 px-6 py-4 text-center shadow-lg">
              <p className="text-sm font-semibold text-slate-700 mb-1">
                Sin pacientes {activeLayer} geocodificados
              </p>
              <p className="text-xs text-slate-400">
                Asegúrate de haber corrido la geocodificación.
              </p>
            </div>
          </div>
        )}

        {/* ── Loading Overlay ──────────────────────────────────────────── */}
        {loading && (
          <div className="absolute inset-0 bg-slate-50/80 backdrop-blur-sm flex items-center justify-center z-[999] rounded-b-2xl">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-3 border-teal-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs font-medium text-slate-500">Cargando mapa…</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Legend ─────────────────────────────────────────────────────── */}
      <div className="absolute bottom-6 right-3 z-[1000] bg-white/90 backdrop-blur-sm border border-slate-200 rounded-xl px-3 py-2 shadow-sm">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
          Densidad ({activeLayer})
        </p>
        <div className="flex items-center gap-1 w-32 h-3 rounded overflow-hidden">
          {activeLayer === 'tamizados' ? (
            <>
              <div className="flex-1 h-full bg-teal-300"></div>
              <div className="flex-1 h-full bg-teal-500"></div>
              <div className="flex-1 h-full bg-teal-600"></div>
              <div className="flex-1 h-full bg-teal-700"></div>
            </>
          ) : (
            <>
              <div className="flex-1 h-full bg-red-300"></div>
              <div className="flex-1 h-full bg-red-500"></div>
              <div className="flex-1 h-full bg-red-600"></div>
              <div className="flex-1 h-full bg-red-700"></div>
            </>
          )}
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[9px] text-slate-400">Baja</span>
          <span className="text-[9px] text-slate-400">Alta</span>
        </div>
      </div>
    </div>
  )
}
