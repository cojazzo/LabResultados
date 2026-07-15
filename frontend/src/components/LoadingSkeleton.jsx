export function SkeletonCard() {
  return (
    <div className="rounded-2xl bg-white p-5 space-y-3">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <div className="h-3 w-24 rounded skeleton-shimmer" />
          <div className="h-8 w-20 rounded skeleton-shimmer" />
        </div>
        <div className="w-11 h-11 rounded-xl skeleton-shimmer" />
      </div>
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 6 }) {
  return (
    <div className="rounded-2xl bg-white overflow-hidden">
      {/* Header */}
      <div className="grid gap-4 px-5 py-4 border-b border-slate-100" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-3 rounded skeleton-shimmer" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="grid gap-4 px-5 py-3.5 border-b border-slate-50"
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="h-3 rounded skeleton-shimmer" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="rounded-2xl bg-white p-5 space-y-4">
      <div className="h-4 w-40 rounded skeleton-shimmer" />
      <div className="h-48 rounded-xl skeleton-shimmer" />
    </div>
  )
}

export default function LoadingSkeleton({ type = 'card', ...props }) {
  switch (type) {
    case 'table': return <SkeletonTable {...props} />
    case 'chart': return <SkeletonChart {...props} />
    default:      return <SkeletonCard {...props} />
  }
}
