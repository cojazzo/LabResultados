const variants = {
  // Interpretación
  normal:  'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  alto:    'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  bajo:    'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  critico: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  // Estados
  enviado:   'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  pendiente: 'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200',
  fallido:   'bg-red-50 text-red-700 ring-1 ring-red-200',
  // Upload states
  completado: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  parcial:    'bg-yellow-50 text-yellow-700 ring-1 ring-yellow-200',
  error:      'bg-red-50 text-red-700 ring-1 ring-red-200',
  // Generic
  activa:   'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  inactiva: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
  info:     'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
}

export default function Badge({ variant = 'info', children, className = '' }) {
  const classes = variants[variant] || variants.info
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${classes} ${className}`}
    >
      {children}
    </span>
  )
}
