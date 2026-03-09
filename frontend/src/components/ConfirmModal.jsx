import { useEffect } from 'react'

/**
 * Reusable confirmation modal.
 *
 * Props:
 *   open          bool
 *   title         string
 *   body          string | ReactNode
 *   confirmLabel  string  (default "Delete")
 *   danger        bool    (default true — red confirm button)
 *   onConfirm     () => void
 *   onCancel      () => void
 */
export default function ConfirmModal({
  open,
  title,
  body,
  confirmLabel = 'Delete',
  danger = true,
  onConfirm,
  onCancel,
}) {
  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-2">{title}</h2>
        <p className="text-sm text-slate-600 mb-6">{body}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-sm rounded font-medium text-white transition-colors
              ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-indigo-600 hover:bg-indigo-700'}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
