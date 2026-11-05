// Semáforo de riesgo renal KDIGO: personas por TFG (G) × albuminuria (A).
// Los colores vienen del backend (misma clasificación que el reporte PDF del paciente).

const ESTILOS = {
  green: { activa: 'bg-emerald-500 text-white', tenue: 'bg-emerald-50 text-emerald-300' },
  yellow: { activa: 'bg-amber-400 text-amber-950', tenue: 'bg-amber-50 text-amber-300' },
  orange: { activa: 'bg-orange-500 text-white', tenue: 'bg-orange-50 text-orange-300' },
  red: { activa: 'bg-red-600 text-white', tenue: 'bg-red-50 text-red-300' },
  gray: { activa: 'bg-slate-400 text-white', tenue: 'bg-slate-50 text-slate-300' },
}

const RIESGOS = [
  { clave: 'bajo', etiqueta: 'Bajo', punto: 'bg-emerald-500' },
  { clave: 'moderado', etiqueta: 'Moderado', punto: 'bg-amber-400' },
  { clave: 'alto', etiqueta: 'Alto', punto: 'bg-orange-500' },
  { clave: 'muy_alto', etiqueta: 'Muy alto', punto: 'bg-red-600' },
]

const RANGO_G = {
  G1: 'TFG ≥ 90',
  G2: '60–89',
  G3a: '45–59',
  G3b: '30–44',
  G4: '15–29',
  G5: '< 15',
  'Sin TFG': 'sin creatinina sérica',
}

const RANGO_A = {
  A1: 'ACR < 30',
  A2: '30–300',
  A3: '> 300',
  'Sin ACR': 'sin ACR',
}

export default function KdigoSemaforo({ data }) {
  if (!data || data.total_personas === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-sm text-slate-400 py-10">
        Sin resultados de función renal en este periodo.
      </div>
    )
  }

  const porCelda = new Map(data.celdas.map((c) => [`${c.g}|${c.a}`, c]))
  const clasificadas = data.total_personas - data.sin_clasificar

  return (
    <div className="flex-1 flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-1.5 text-center">
          <thead>
            <tr>
              <th />
              {data.columnas.map((a) => (
                <th key={a} className="pb-1 align-bottom">
                  <div className="text-xs font-bold text-slate-700">{a}</div>
                  <div className="text-[10px] font-normal text-slate-400">{RANGO_A[a]}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.filas.map((g) => (
              <tr key={g}>
                <th className="pr-2 text-right whitespace-nowrap">
                  <div className="text-xs font-bold text-slate-700">{g}</div>
                  <div className="text-[10px] font-normal text-slate-400">{RANGO_G[g]}</div>
                </th>
                {data.columnas.map((a) => {
                  const celda = porCelda.get(`${g}|${a}`)
                  if (!celda) {
                    return <td key={a} className="rounded-lg bg-slate-50" />
                  }
                  const estilo = ESTILOS[celda.color] || ESTILOS.gray
                  const pct = clasificadas ? Math.round((celda.cantidad / clasificadas) * 100) : 0
                  return (
                    <td
                      key={a}
                      title={`${g} / ${a}: ${celda.cantidad} personas`}
                      className={`rounded-lg px-2 py-2 min-w-[64px] ${
                        celda.cantidad > 0 ? estilo.activa : estilo.tenue
                      }`}
                    >
                      <div className="text-lg font-extrabold leading-none">{celda.cantidad}</div>
                      {celda.cantidad > 0 && (
                        <div className="text-[10px] opacity-80 mt-0.5">{pct}%</div>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
        {RIESGOS.map((r) => (
          <span key={r.clave} className="inline-flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${r.punto}`} />
            {r.etiqueta}: <b className="text-slate-800">{data.por_riesgo[r.clave]}</b>
          </span>
        ))}
      </div>

      <p className="text-[11px] text-slate-400 leading-snug">
        Cada persona cuenta una vez, con su determinación más reciente del periodo. Los niveles de
        riesgo suman solo a quienes tienen TFG y ACR ({data.completas}). La fila «Sin TFG» agrupa a
        quienes solo cuentan con ACR
        {data.sin_clasificar > 0 && `; ${data.sin_clasificar} persona(s) no tienen ni TFG ni ACR`}.
      </p>
    </div>
  )
}
