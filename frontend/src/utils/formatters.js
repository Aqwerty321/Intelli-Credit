// ── Shared formatting utilities ──────────────────────────────────────────────

export function asNumber(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

export function formatRiskScore(value) {
  const num = asNumber(value)
  return num == null ? '—' : num.toFixed(2)
}

export function formatPercent(value, digits = 0) {
  const num = asNumber(value)
  return num == null ? '—' : `${num.toFixed(digits)}%`
}

export function formatCurrency(value) {
  const num = asNumber(value)
  return num == null ? '—' : `₹${num.toLocaleString('en-IN')}`
}

export function formatLabel(value) {
  if (!value) return 'Unavailable'
  return String(value).replaceAll('_', ' ')
}

export function riskBand(value) {
  const num = asNumber(value)
  if (num == null) return 'Pending'
  if (num < 0.4) return 'Low Risk'
  if (num < 0.7) return 'Watchlist'
  return 'High Risk'
}

export function relativeTime(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return new Date(isoStr).toLocaleDateString()
}

export function uniqueLines(items) {
  return [...new Set((items || []).filter(Boolean))]
}

// ── Style constants ──────────────────────────────────────────────────────────

export const VERDICT_STYLE = {
  APPROVE: 'bg-green-50 border-green-400 text-green-800',
  CONDITIONAL: 'bg-amber-50 border-amber-400 text-amber-800',
  REJECT: 'bg-red-50 border-red-400 text-red-800',
}

export const VERDICT_DOT = {
  APPROVE: 'bg-green-500',
  CONDITIONAL: 'bg-amber-500',
  REJECT: 'bg-red-500',
}

export const VERDICT_TEXT = {
  APPROVE: 'text-green-700',
  CONDITIONAL: 'text-amber-700',
  REJECT: 'text-red-700',
}

export const RISK_COLOR = (score) => {
  if (score == null) return 'text-slate-400'
  if (score < 0.4) return 'text-green-600'
  if (score < 0.6) return 'text-amber-600'
  return 'text-red-600'
}

export const SEVERITY_BADGE = {
  HIGH: 'bg-red-100 text-red-700',
  MEDIUM: 'bg-yellow-100 text-yellow-700',
  LOW: 'bg-blue-100 text-blue-700',
  CRITICAL: 'bg-red-200 text-red-900',
}

export const SOURCE_TIER_BADGE = {
  authoritative: 'bg-green-100 text-green-700 border-green-300',
  credible: 'bg-blue-100 text-blue-700 border-blue-300',
  general: 'bg-slate-100 text-slate-600 border-slate-300',
  low: 'bg-red-50 text-red-500 border-red-200',
}

export const IMPACT_STYLE = {
  negative: { border: 'border-red-400', badge: 'bg-red-100 text-red-700' },
  positive: { border: 'border-green-400', badge: 'bg-green-100 text-green-700' },
  neutral: { border: 'border-slate-300', badge: 'bg-slate-100 text-slate-600' },
  unverified: { border: 'border-amber-300', badge: 'bg-amber-100 text-amber-700' },
}

export const NOTE_TYPE_BADGE = {
  general: 'bg-slate-100 text-slate-700',
  risk: 'bg-red-100 text-red-700',
  approval: 'bg-green-100 text-green-700',
  escalation: 'bg-amber-100 text-amber-700',
}

export const PIPELINE_PHASES = [
  { key: 'ingestion', label: 'Ingestion' },
  { key: 'research', label: 'Research' },
  { key: 'reasoning', label: 'Reasoning' },
  { key: 'decision', label: 'Decision' },
]

// ── Notes helpers ─────────────────────────────────────────────────────────────

export const EMPTY_NOTE_FORM = { author: '', text: '', note_type: 'general', tags_raw: '', pinned: false }

export function sortNotes(notes) {
  const pinned = [...notes.filter(n => n.pinned)].sort((a, b) => b.created_at.localeCompare(a.created_at))
  const unpinned = [...notes.filter(n => !n.pinned)].sort((a, b) => b.created_at.localeCompare(a.created_at))
  return [...pinned, ...unpinned]
}

export function applyNoteFilters(notes, { type, keyword, tags }) {
  return notes.filter(n => {
    if (type && n.note_type !== type) return false
    if (keyword) {
      const kw = keyword.toLowerCase()
      if (!n.text.toLowerCase().includes(kw) && !n.author.toLowerCase().includes(kw)) return false
    }
    if (tags.length > 0 && !tags.some(t => (n.tags || []).includes(t))) return false
    return true
  })
}
