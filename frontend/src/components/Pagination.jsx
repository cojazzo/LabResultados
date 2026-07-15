import { ChevronLeft, ChevronRight } from 'lucide-react'

export default function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  const pages = []
  const range = 2
  for (let i = Math.max(1, page - range); i <= Math.min(totalPages, page + range); i++) {
    pages.push(i)
  }

  return (
    <div className="flex items-center justify-center gap-1.5 mt-6">
      <button
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        className="flex items-center justify-center w-9 h-9 rounded-lg text-sm font-medium text-slate-500 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      {pages[0] > 1 && (
        <>
          <button
            onClick={() => onPageChange(1)}
            className="flex items-center justify-center w-9 h-9 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition"
          >
            1
          </button>
          {pages[0] > 2 && (
            <span className="px-1 text-slate-300">…</span>
          )}
        </>
      )}

      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onPageChange(p)}
          className={`flex items-center justify-center w-9 h-9 rounded-lg text-sm font-medium transition ${
            p === page
              ? 'bg-[var(--color-primary-600)] text-white shadow-md'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          {p}
        </button>
      ))}

      {pages[pages.length - 1] < totalPages && (
        <>
          {pages[pages.length - 1] < totalPages - 1 && (
            <span className="px-1 text-slate-300">…</span>
          )}
          <button
            onClick={() => onPageChange(totalPages)}
            className="flex items-center justify-center w-9 h-9 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 transition"
          >
            {totalPages}
          </button>
        </>
      )}

      <button
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        className="flex items-center justify-center w-9 h-9 rounded-lg text-sm font-medium text-slate-500 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  )
}
