export default function StatCard({
  icon: Icon,
  value,
  label,
  trend,
  trendUp,
  color = 'from-primary-500 to-primary-700',
  delay = 0,
}) {
  return (
    <div
      className="gradient-border group animate-fade-in-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="relative bg-white rounded-2xl p-5 h-full transition-shadow duration-300 hover:shadow-xl hover:shadow-slate-200/60">
        {/* Decorative glow */}
        <div className={`absolute -top-px -right-px w-20 h-20 bg-gradient-to-br ${color} opacity-[0.07] rounded-tr-2xl rounded-bl-[60px] pointer-events-none`} />

        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              {label}
            </p>
            <p className="text-3xl font-extrabold text-slate-800 animate-count-up">
              {value}
            </p>
            {trend !== undefined && (
              <div className={`flex items-center gap-1 text-xs font-medium ${trendUp ? 'text-emerald-600' : 'text-red-500'}`}>
                <span>{trendUp ? '↑' : '↓'}</span>
                <span>{trend}</span>
              </div>
            )}
          </div>
          {Icon && (
            <div className={`flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br ${color} text-white shadow-lg shadow-slate-300/30 group-hover:scale-110 transition-transform duration-300`}>
              <Icon className="w-5 h-5" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
