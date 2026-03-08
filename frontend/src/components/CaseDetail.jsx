import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ConfirmModal from './ConfirmModal'
import {
  getCase,
  uploadDocument,
  listNotes,
  addNote,
  updateNote,
  deleteNote,
  deleteCase,
  runSync,
  streamRunUrl,
  downloadCAMUrl,
} from '../services/api'

const VERDICT_STYLE = {
  APPROVE: 'bg-green-50 border-green-400 text-green-800',
  CONDITIONAL: 'bg-yellow-50 border-yellow-400 text-yellow-800',
  REJECT: 'bg-red-50 border-red-400 text-red-800',
}

const RISK_COLOR = (score) => {
  if (score == null) return 'text-gray-400'
  if (score < 0.4) return 'text-green-600'
  if (score < 0.6) return 'text-yellow-600'
  return 'text-red-600'
}

const SEVERITY_BADGE = {
  HIGH: 'bg-red-100 text-red-700',
  MEDIUM: 'bg-yellow-100 text-yellow-700',
  LOW: 'bg-blue-100 text-blue-700',
  CRITICAL: 'bg-red-200 text-red-900',
}

const SOURCE_TIER_BADGE = {
  authoritative: 'bg-green-100 text-green-700 border-green-300',
  credible: 'bg-blue-100 text-blue-700 border-blue-300',
  general: 'bg-gray-100 text-gray-600 border-gray-300',
  low: 'bg-red-50 text-red-500 border-red-200',
}

const IMPACT_STYLE = {
  negative: { border: 'border-red-400', badge: 'bg-red-100 text-red-700' },
  positive: { border: 'border-green-400', badge: 'bg-green-100 text-green-700' },
  neutral: { border: 'border-gray-300', badge: 'bg-gray-100 text-gray-600' },
  unverified: { border: 'border-amber-300', badge: 'bg-amber-100 text-amber-700' },
}

const PIPELINE_PHASES = [
  { key: 'ingestion', label: 'Ingestion', ssePhrases: ['ingestion'] },
  { key: 'research', label: 'Research', ssePhrases: ['research', 'research_complete'] },
  { key: 'reasoning', label: 'Reasoning', ssePhrases: ['reasoning'] },
  { key: 'decision', label: 'Decision', ssePhrases: ['DONE'] },
]

function PipelineTimeline({ log }) {
  const reached = new Set()
  log.forEach(l => {
    const phase = (l.phase || '').toLowerCase()
    if (phase.includes('ingestion')) reached.add('ingestion')
    if (phase.includes('research') || phase === 'research_complete') {
      reached.add('ingestion')
      reached.add('research')
    }
    if (phase.includes('reasoning')) {
      reached.add('ingestion')
      reached.add('research')
      reached.add('reasoning')
    }
    if (phase === 'done') PIPELINE_PHASES.forEach(p => reached.add(p.key))
  })

  return (
    <div className="flex items-start gap-0 mb-5">
      {PIPELINE_PHASES.map((p, i) => (
        <div key={p.key} className="flex items-center">
          <div className="flex flex-col items-center w-20">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors
              ${reached.has(p.key)
                ? 'bg-indigo-600 border-indigo-600 text-white'
                : 'bg-white border-gray-300 text-gray-400'}`}>
              {reached.has(p.key) ? '✓' : i + 1}
            </div>
            <span className={`text-xs mt-1 text-center leading-tight ${reached.has(p.key) ? 'text-indigo-700 font-medium' : 'text-gray-400'}`}>
              {p.label}
            </span>
          </div>
          {i < PIPELINE_PHASES.length - 1 && (
            <div className={`h-0.5 w-8 mb-4 mx-1 transition-colors ${reached.has(PIPELINE_PHASES[i + 1].key) ? 'bg-indigo-500' : 'bg-gray-200'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

function CollapsibleInputs({ inputs }) {
  const [open, setOpen] = useState(false)
  if (!inputs || !Object.keys(inputs).length) return null
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(o => !o)} className="text-xs text-indigo-500 hover:underline">
        {open ? '▾ Hide inputs' : '▸ Show inputs'}
      </button>
      {open && (
        <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 bg-gray-50 rounded p-2 text-xs font-mono">
          {Object.entries(inputs).map(([k, v]) => (
            <div key={k} className="flex gap-1">
              <span className="text-gray-400">{k}:</span>
              <span className="text-gray-700">{JSON.stringify(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Style constants ──────────────────────────────────────────────────────────

const NOTE_TYPE_BADGE = {
  general: 'bg-gray-100 text-gray-700',
  risk: 'bg-red-100 text-red-700',
  approval: 'bg-green-100 text-green-700',
  escalation: 'bg-amber-100 text-amber-700',
}

// ── Notes helpers ─────────────────────────────────────────────────────────────

const EMPTY_NOTE_FORM = { author: '', text: '', note_type: 'general', tags_raw: '', pinned: false }

function sortNotes(notes) {
  const pinned = [...notes.filter(n => n.pinned)].sort((a, b) => b.created_at.localeCompare(a.created_at))
  const unpinned = [...notes.filter(n => !n.pinned)].sort((a, b) => b.created_at.localeCompare(a.created_at))
  return [...pinned, ...unpinned]
}

function applyNoteFilters(notes, { type, keyword, tags }) {
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

function relativeTime(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return new Date(isoStr).toLocaleDateString()
}

export default function CaseDetail() {
  const { caseId } = useParams()
  const navigate = useNavigate()

  // Core state
  const [caseData, setCaseData] = useState(null)
  const [tab, setTab] = useState('documents')
  const [uploading, setUploading] = useState(false)

  // SSE run
  const [running, setRunning] = useState(false)
  const [log, setLog] = useState([])
  const [sseError, setSseError] = useState(false)
  const logRef = useRef(null)
  const fileRef = useRef(null)
  const esRef = useRef(null)

  // Sync run
  const [runningSync, setRunningSync] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [syncError, setSyncError] = useState('')

  // Notes
  const [notesList, setNotesList] = useState([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [noteFilter, setNoteFilter] = useState({ type: '', keyword: '', tags: [] })
  const [noteForm, setNoteForm] = useState(EMPTY_NOTE_FORM)
  const [noteEditId, setNoteEditId] = useState(null)
  const [noteSubmitting, setNoteSubmitting] = useState(false)
  const [noteDeleteId, setNoteDeleteId] = useState(null)

  // Case delete
  const [showDeleteCase, setShowDeleteCase] = useState(false)

  const reload = useCallback(() =>
    getCase(caseId).then(setCaseData).catch(() => {}), [caseId])

  const reloadNotes = useCallback(() => {
    setNotesLoading(true)
    listNotes(caseId).then(ns => { setNotesList(ns); setNotesLoading(false) }).catch(() => setNotesLoading(false))
  }, [caseId])

  useEffect(() => { reload() }, [reload])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log])
  useEffect(() => { if (tab === 'notes') reloadNotes() }, [tab, reloadNotes])
  // Clean up SSE on unmount
  useEffect(() => () => { if (esRef.current) { esRef.current.close(); esRef.current = null } }, [])

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    try { await uploadDocument(caseId, file) } finally { setUploading(false) }
    await reload()
  }

  const handleRun = () => {
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    setRunning(true)
    setSseError(false)
    setSyncResult(null)
    setLog([])
    setTab('run')
    const es = new EventSource(streamRunUrl(caseId))
    esRef.current = es
    const addLog = (data) => setLog(l => [...l, data])
    es.addEventListener('progress', e => addLog(JSON.parse(e.data)))
    es.addEventListener('research_complete', e => addLog({ phase: 'research_complete', ...JSON.parse(e.data) }))
    es.addEventListener('research_plan_ready', e => addLog({ phase: 'research_plan_ready', ...JSON.parse(e.data) }))
    es.addEventListener('evidence_scored', e => addLog({ phase: 'evidence_scored', ...JSON.parse(e.data) }))
    es.addEventListener('claim_graph_ready', e => addLog({ phase: 'claim_graph_ready', ...JSON.parse(e.data) }))
    es.addEventListener('counterfactual_ready', e => addLog({ phase: 'counterfactual_ready', ...JSON.parse(e.data) }))
    es.addEventListener('warning', e => addLog({ phase: 'warning', ...JSON.parse(e.data) }))
    es.addEventListener('complete', e => {
      addLog({ phase: 'DONE', ...JSON.parse(e.data) })
      setRunning(false)
      es.close(); esRef.current = null
      reload()
    })
    es.addEventListener('error', e => {
      addLog({ phase: 'ERROR', message: typeof e.data === 'string' ? e.data : 'Connection error' })
      setRunning(false)
      setSseError(true)
      es.close(); esRef.current = null
    })
  }

  const handleSyncRun = async () => {
    setRunningSync(true)
    setSyncError('')
    setSyncResult(null)
    try {
      const result = await runSync(caseId)
      setSyncResult(result)
      await reload()
    } catch (err) {
      setSyncError(err.message || 'Sync run failed')
    } finally {
      setRunningSync(false)
    }
  }

  const handleDeleteCase = async () => {
    await deleteCase(caseId)
    navigate('/')
  }

  const handleNoteSubmit = async (e) => {
    e.preventDefault()
    if (!noteForm.author.trim() || !noteForm.text.trim()) return
    setNoteSubmitting(true)
    const payload = {
      author: noteForm.author.trim(),
      text: noteForm.text.trim(),
      note_type: noteForm.note_type,
      tags: noteForm.tags_raw.split(',').map(t => t.trim()).filter(Boolean),
      pinned: noteForm.pinned,
    }
    try {
      if (noteEditId) {
        await updateNote(caseId, noteEditId, payload)
        setNoteEditId(null)
      } else {
        await addNote(caseId, payload)
      }
      setNoteForm(EMPTY_NOTE_FORM)
      reloadNotes()
    } finally {
      setNoteSubmitting(false)
    }
  }

  const handleNoteEdit = (note) => {
    setNoteEditId(note.note_id)
    setNoteForm({
      author: note.author,
      text: note.text,
      note_type: note.note_type,
      tags_raw: (note.tags || []).join(', '),
      pinned: note.pinned || false,
    })
  }

  const handleNoteDelete = async () => {
    if (!noteDeleteId) return
    await deleteNote(caseId, noteDeleteId)
    setNoteDeleteId(null)
    reloadNotes()
  }

  const toggleTagFilter = (tag) => {
    setNoteFilter(f => ({
      ...f,
      tags: f.tags.includes(tag) ? f.tags.filter(t => t !== tag) : [...f.tags, tag],
    }))
  }

  if (!caseData) return <p className="text-gray-500 py-10 text-center">Loading…</p>

  const trace = caseData.trace || {}
  const decision = trace.decision || {}
  const firings = trace.rule_firings || []
  const minRiskPolicy = trace.minimum_risk_policy || []
  const graphTrace = trace.graph_trace || null
  const research = caseData.research || {}
  const findings = research.findings || []
  const hasRun = !!decision.recommendation

  const isV3 = trace.schema_version === 'v3'
  const evidenceJudge = trace.evidence_judge || null
  const claimGraph = trace.claim_graph || null
  const counterfactuals = trace.counterfactuals || null
  const searchPlan = trace.research_plan || null

  const tabs = [
    'documents', 'run', 'notes', 'evidence', 'trace', 'cam',
    ...(hasRun && isV3 ? ['judge'] : []),
  ]

  const allNoteTags = [...new Set(notesList.flatMap(n => n.tags || []))]
  const filteredNotes = applyNoteFilters(sortNotes(notesList), noteFilter)

  return (
    <div>
      {/* Confirm modals */}
      <ConfirmModal
        open={showDeleteCase}
        title="Delete Case"
        body={`This will permanently delete all files for "${caseData.company_name}". This cannot be undone.`}
        confirmLabel="Delete Case"
        onConfirm={handleDeleteCase}
        onCancel={() => setShowDeleteCase(false)}
      />
      <ConfirmModal
        open={!!noteDeleteId}
        title="Delete Note"
        body="This note will be permanently removed."
        confirmLabel="Delete Note"
        onConfirm={handleNoteDelete}
        onCancel={() => setNoteDeleteId(null)}
      />

      {/* Header */}
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{caseData.company_name}</h1>
          <p className="text-gray-500 text-sm mt-1">
            ₹{Number(caseData.loan_amount).toLocaleString('en-IN')} · {caseData.loan_purpose}
            {caseData.sector && ` · ${caseData.sector}`}
            {caseData.location && `, ${caseData.location}`}
          </p>
        </div>
        <button
          onClick={() => setShowDeleteCase(true)}
          className="shrink-0 text-sm text-red-500 hover:text-red-700 hover:underline transition-colors"
        >
          🗑 Delete Case
        </button>
      </div>

      {/* Verdict banner */}
      {hasRun && (
        <div className={`rounded-lg border-l-4 p-4 mb-5 ${VERDICT_STYLE[decision.recommendation] || ''}`}>
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-2xl font-bold">{decision.recommendation}</span>
            <span className={`text-xl font-mono font-semibold ${RISK_COLOR(decision.risk_score)}`}>
              Risk: {decision.risk_score?.toFixed(2)}
            </span>
            {decision.recommended_amount > 0 && (
              <span className="text-sm">Sanction: ₹{Number(decision.recommended_amount).toLocaleString('en-IN')}</span>
            )}
            <span className="text-xs text-gray-500 ml-auto">{firings.length} rule{firings.length !== 1 ? 's' : ''} fired · {findings.length} evidence item{findings.length !== 1 ? 's' : ''}</span>
          </div>
        </div>
      )}

      {/* Sync result banner */}
      {syncResult && !running && (
        <div className="rounded border border-indigo-200 bg-indigo-50 px-4 py-2 mb-4 text-sm flex items-center gap-3">
          <span className="font-medium text-indigo-700">Sync run complete:</span>
          <span className={`font-semibold ${syncResult.recommendation === 'APPROVE' ? 'text-green-700' : syncResult.recommendation === 'CONDITIONAL' ? 'text-yellow-700' : 'text-red-700'}`}>
            {syncResult.recommendation}
          </span>
          <span className="text-gray-500">Risk: {syncResult.risk_score?.toFixed(2)}</span>
          <button onClick={() => setSyncResult(null)} className="ml-auto text-gray-400 hover:text-gray-600 text-xs">✕</button>
        </div>
      )}

      {/* Run buttons */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          onClick={handleRun}
          disabled={running || runningSync || !caseData.documents?.length}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors"
        >
          {running ? '⏳ Running…' : hasRun ? '↺ Re-run Appraisal' : '▶ Run Appraisal'}
        </button>
        <button
          onClick={handleSyncRun}
          disabled={running || runningSync || !caseData.documents?.length}
          className="px-4 py-2 bg-gray-700 text-white text-sm rounded font-medium hover:bg-gray-800 disabled:opacity-40 transition-colors"
          title="Blocking synchronous run — no streaming"
        >
          {runningSync ? '⏳ Sync…' : 'Run (Sync)'}
        </button>
        {!caseData.documents?.length && <span className="text-xs text-gray-400">Upload documents first</span>}
        {syncError && <span className="text-xs text-red-600">⚠ {syncError}</span>}
        {hasRun && !running && !runningSync && (
          <span className="text-xs text-gray-400">Last run: {trace.timestamp ? new Date(trace.timestamp).toLocaleString() : 'unknown'}</span>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="flex gap-1 flex-wrap">
          {tabs.map(t => (
            <button key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium rounded-t transition-colors capitalize
                ${tab === t ? 'bg-white border border-b-white text-indigo-600 -mb-px' : 'text-gray-500 hover:text-gray-700'}`}>
              {t}
              {t === 'trace' && firings.length > 0 && <span className="ml-1 text-xs bg-indigo-100 text-indigo-600 px-1 rounded">{firings.length}</span>}
              {t === 'evidence' && findings.length > 0 && <span className="ml-1 text-xs bg-gray-100 text-gray-500 px-1 rounded">{findings.length}</span>}
              {t === 'notes' && notesList.length > 0 && <span className="ml-1 text-xs bg-gray-100 text-gray-500 px-1 rounded">{notesList.length}</span>}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab: Documents */}
      {tab === 'documents' && (
        <div>
          <h2 className="font-medium mb-3">Uploaded Documents</h2>
          {caseData.documents?.length ? (
            <ul className="space-y-2 mb-4">
              {caseData.documents.map(d => (
                <li key={d} className="flex items-center gap-2 bg-white border rounded px-3 py-2 text-sm">
                  <span className="text-blue-500">📄</span>{d}
                </li>
              ))}
            </ul>
          ) : <p className="text-gray-400 mb-4 text-sm">No documents uploaded yet.</p>}

          <label className={`inline-flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
            <input ref={fileRef} type="file" accept=".pdf,.json,.txt,.md" className="hidden" onChange={handleUpload} disabled={uploading} />
            {uploading ? 'Uploading…' : '+ Upload document'}
          </label>
          <p className="text-xs text-gray-400 mt-2">Supported: PDF, JSON, TXT, MD</p>
        </div>
      )}

      {/* Tab: Run */}
      {tab === 'run' && (
        <div>
          <PipelineTimeline log={log} />
          <h2 className="font-medium mb-3">Pipeline Log</h2>
          <div ref={logRef} className="bg-gray-950 text-green-300 rounded p-4 h-64 overflow-y-auto font-mono text-xs space-y-0.5">
            {log.length === 0 && <span className="text-gray-500">Click "Run Appraisal" to start…</span>}
            {log.map((l, i) => {
              const ph = (l.phase || '').toUpperCase()
              const color = ph === 'ERROR' ? 'text-red-400' : ph === 'DONE' ? 'text-yellow-300 font-bold' : ph === 'WARNING' ? 'text-amber-400' : ''
              return (
                <div key={i} className={color}>
                  [{ph}] {l.message || l.findings_count != null ? `${l.message || ''}${l.findings_count != null ? ` — ${l.findings_count} findings (${l.negative_count} negative)` : ''}` : JSON.stringify(l)}
                </div>
              )
            })}
          </div>
          {running && <p className="text-xs text-gray-400 mt-2 animate-pulse">Pipeline running…</p>}
          {sseError && (
            <div className="mt-3 flex items-center gap-3 text-sm bg-amber-50 border border-amber-200 rounded px-4 py-2">
              <span className="text-amber-700">⚠ Stream failed — try sync fallback?</span>
              <button
                onClick={handleSyncRun}
                disabled={runningSync}
                className="px-3 py-1 bg-gray-700 text-white rounded text-xs hover:bg-gray-800 disabled:opacity-40"
              >
                {runningSync ? '⏳ Running…' : 'Run Sync'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab: Notes */}
      {tab === 'notes' && (
        <div className="space-y-4">
          {/* Filter bar */}
          <div className="flex flex-wrap gap-3 items-end bg-gray-50 border rounded p-3">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Type</label>
              <select
                value={noteFilter.type}
                onChange={e => setNoteFilter(f => ({ ...f, type: e.target.value }))}
                className="text-sm border rounded px-2 py-1 bg-white"
              >
                <option value="">All types</option>
                <option value="general">General</option>
                <option value="risk">Risk</option>
                <option value="approval">Approval</option>
                <option value="escalation">Escalation</option>
              </select>
            </div>
            <div className="flex-1 min-w-40">
              <label className="text-xs text-gray-500 block mb-1">Search</label>
              <input
                type="text"
                placeholder="Keyword…"
                value={noteFilter.keyword}
                onChange={e => setNoteFilter(f => ({ ...f, keyword: e.target.value }))}
                className="w-full text-sm border rounded px-2 py-1"
              />
            </div>
            {allNoteTags.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Tags (OR)</p>
                <div className="flex flex-wrap gap-1">
                  {allNoteTags.map(tag => (
                    <button
                      key={tag}
                      onClick={() => toggleTagFilter(tag)}
                      className={`text-xs px-2 py-0.5 rounded-full border transition-colors
                        ${noteFilter.tags.includes(tag)
                          ? 'bg-indigo-600 text-white border-indigo-600'
                          : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'}`}
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {(noteFilter.type || noteFilter.keyword || noteFilter.tags.length > 0) && (
              <button
                onClick={() => setNoteFilter({ type: '', keyword: '', tags: [] })}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Clear filters
              </button>
            )}
          </div>

          {/* Add / Edit form */}
          <form onSubmit={handleNoteSubmit} className="bg-white border rounded p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-700">{noteEditId ? 'Edit Note' : 'Add Note'}</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Author</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Priya Singh"
                  value={noteForm.author}
                  onChange={e => setNoteForm(f => ({ ...f, author: e.target.value }))}
                  className="w-full text-sm border rounded px-2 py-1"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">Type</label>
                <select
                  value={noteForm.note_type}
                  onChange={e => setNoteForm(f => ({ ...f, note_type: e.target.value }))}
                  className="w-full text-sm border rounded px-2 py-1 bg-white"
                >
                  <option value="general">General</option>
                  <option value="risk">Risk</option>
                  <option value="approval">Approval</option>
                  <option value="escalation">Escalation</option>
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Note</label>
              <textarea
                required
                rows={3}
                placeholder="Enter note text…"
                value={noteForm.text}
                onChange={e => setNoteForm(f => ({ ...f, text: e.target.value }))}
                className="w-full text-sm border rounded px-2 py-1 resize-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-3 items-end">
              <div>
                <label className="text-xs text-gray-500 block mb-1">Tags <span className="text-gray-400">(comma-separated, max 5)</span></label>
                <input
                  type="text"
                  placeholder="e.g. verified, promoter, gst"
                  value={noteForm.tags_raw}
                  onChange={e => setNoteForm(f => ({ ...f, tags_raw: e.target.value }))}
                  className="w-full text-sm border rounded px-2 py-1"
                />
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer pb-1">
                <input
                  type="checkbox"
                  checked={noteForm.pinned}
                  onChange={e => setNoteForm(f => ({ ...f, pinned: e.target.checked }))}
                  className="rounded"
                />
                <span className="text-gray-700">📌 Pin note</span>
              </label>
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={noteSubmitting}
                className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-40"
              >
                {noteSubmitting ? 'Saving…' : noteEditId ? 'Save changes' : 'Add note'}
              </button>
              {noteEditId && (
                <button
                  type="button"
                  onClick={() => { setNoteEditId(null); setNoteForm(EMPTY_NOTE_FORM) }}
                  className="px-4 py-1.5 text-sm rounded border border-gray-300 text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>

          {/* Notes list */}
          {notesLoading ? (
            <p className="text-gray-400 text-sm text-center py-4">Loading notes…</p>
          ) : filteredNotes.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">
              {notesList.length === 0 ? 'No notes yet. Add one above.' : 'No notes match the current filters.'}
            </p>
          ) : (
            <div className="space-y-3">
              {filteredNotes.map(note => {
                const isEdited = note.updated_at && note.updated_at !== note.created_at
                return (
                  <div
                    key={note.note_id}
                    className={`bg-white rounded border px-4 py-3 ${note.pinned ? 'border-l-4 border-l-amber-400' : ''}`}
                  >
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      {note.pinned && <span className="text-amber-500 text-xs">📌</span>}
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded capitalize ${NOTE_TYPE_BADGE[note.note_type] || NOTE_TYPE_BADGE.general}`}>
                        {note.note_type}
                      </span>
                      <span className="text-xs font-medium text-gray-700">{note.author}</span>
                      <span className="text-xs text-gray-400">{relativeTime(note.created_at)}</span>
                      {isEdited && <span className="text-xs text-gray-400">(edited {relativeTime(note.updated_at)})</span>}
                      <div className="ml-auto flex gap-2">
                        <button onClick={() => handleNoteEdit(note)} className="text-xs text-indigo-500 hover:underline">Edit</button>
                        <button onClick={() => setNoteDeleteId(note.note_id)} className="text-xs text-red-400 hover:underline">Delete</button>
                      </div>
                    </div>
                    <p className="text-sm text-gray-800 whitespace-pre-wrap">{note.text}</p>
                    {note.tags?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {note.tags.map(tag => (
                          <span key={tag} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">#{tag}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Evidence */}
      {tab === 'evidence' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium">Research Evidence <span className="text-xs text-gray-400">({findings.length} findings)</span></h2>
            {research.corroborated_findings != null && (
              <span className="text-xs text-gray-500">
                {research.corroborated_findings} corroborated · {findings.length - research.corroborated_findings} need more sources
              </span>
            )}
          </div>
          {!findings.length ? (
            <p className="text-gray-400 text-sm">Run the appraisal to collect research evidence.</p>
          ) : (
            <div className="space-y-3">
              {findings.map((f, i) => {
                const imp = IMPACT_STYLE[f.risk_impact] || IMPACT_STYLE.neutral
                const tier = f.source_tier || 'general'
                return (
                  <div key={i} className={`bg-white rounded border-l-4 px-4 py-3 ${imp.border} border border-l-4`}>
                    <div className="flex flex-wrap gap-2 items-center mb-2">
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded uppercase ${imp.badge}`}>
                        {f.risk_impact}
                      </span>
                      <span className={`text-xs px-1.5 py-0.5 rounded border font-medium capitalize ${SOURCE_TIER_BADGE[tier] || SOURCE_TIER_BADGE.general}`}>
                        {tier}
                      </span>
                      <span className="text-xs text-gray-500 uppercase">{f.category}</span>
                      {f.insufficient_corroboration && (
                        <span className="text-xs bg-amber-50 border border-amber-300 text-amber-700 px-1.5 py-0.5 rounded">
                          ⚠ needs corroboration
                        </span>
                      )}
                      {f.novel === true && (
                        <span className="text-xs bg-purple-50 border border-purple-200 text-purple-600 px-1.5 py-0.5 rounded">novel</span>
                      )}
                      <span className="ml-auto text-xs text-gray-400">
                        {f.corroboration_count != null ? `${f.corroboration_count} src` : ''}{' '}
                        conf: {(f.confidence || f.relevance_score || 0).toFixed(2)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-800">{f.summary}</p>
                    <a href={f.source} target="_blank" rel="noreferrer" className="text-xs text-blue-500 hover:underline mt-1 block truncate">{f.source_title || f.source}</a>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Trace */}
      {tab === 'trace' && (
        <div className="space-y-4">
          {/* Graph trace */}
          {graphTrace && (
            <div className="bg-white border rounded px-4 py-3">
              <h3 className="font-medium text-sm mb-2 text-gray-700">Graph Analysis</h3>
              <div className="flex flex-wrap gap-4 text-sm">
                <span className="text-gray-500">Edges examined: <strong>{graphTrace.edges_examined ?? 0}</strong></span>
                <span className="text-gray-500">Suspicious cycles: <strong className={graphTrace.suspicious_cycles > 0 ? 'text-red-600' : ''}>{graphTrace.suspicious_cycles ?? 0}</strong></span>
                {graphTrace.no_graph_evidence && (
                  <span className="text-xs bg-gray-50 border border-gray-200 text-gray-500 px-2 py-0.5 rounded">No transaction graph data — graph evidence unavailable</span>
                )}
                {graphTrace.fraud_alerts?.length > 0 && (
                  <span className="text-xs bg-red-50 border border-red-300 text-red-700 px-1.5 py-0.5 rounded">
                    🚨 {graphTrace.fraud_alerts.length} fraud alert{graphTrace.fraud_alerts.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Rule firings */}
          <div>
            <h2 className="font-medium mb-3">Rule Firings <span className="text-xs text-gray-400">({firings.length} rules fired)</span></h2>
            {!firings.length ? (
              <p className="text-gray-400 text-sm">Run the appraisal first.</p>
            ) : (
              <div className="space-y-3">
                {firings.map((rf, i) => (
                  <div key={i} className="bg-white rounded border px-4 py-3">
                    <div className="flex flex-wrap gap-2 items-center mb-1">
                      <span className="font-mono text-xs text-gray-400">#{rf.rule_id}</span>
                      <span className="font-medium text-sm">{rf.rule_slug}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ${SEVERITY_BADGE[rf.severity] || 'bg-gray-100 text-gray-600'}`}>
                        {rf.severity}
                      </span>
                      <span className="text-xs font-mono text-orange-600 font-semibold">+{rf.risk_adjustment?.toFixed(2)}</span>
                      {rf.hard_reject && <span className="text-xs bg-red-600 text-white px-1.5 py-0.5 rounded font-bold">HARD REJECT</span>}
                    </div>
                    <p className="text-sm text-gray-700 mt-1">{rf.rationale}</p>
                    {rf.missing_data_flags?.length > 0 && (
                      <p className="text-xs text-amber-600 mt-1.5 bg-amber-50 px-2 py-1 rounded">
                        ⚠ Missing data: {rf.missing_data_flags.join(', ')}
                      </p>
                    )}
                    <CollapsibleInputs inputs={rf.inputs} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Minimum risk policy (defaults applied) */}
          {minRiskPolicy.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded px-4 py-3">
              <h3 className="font-medium text-sm text-amber-800 mb-2">Conservative Defaults Applied ({minRiskPolicy.length})</h3>
              <p className="text-xs text-amber-700 mb-2">These fields were not found in uploaded documents. Conservative defaults were used.</p>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                {minRiskPolicy.map((p, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="font-mono text-amber-700">{p.field}</span>
                    <span className="text-amber-600">→ {JSON.stringify(p.default_value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: CAM */}
      {tab === 'cam' && (
        <div>
          <h2 className="font-medium mb-3">Credit Appraisal Memo</h2>
          {hasRun ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                {[
                  ['Recommendation', decision.recommendation],
                  ['Risk Score', decision.risk_score?.toFixed(2)],
                  ['Sanction Amount', decision.recommended_amount > 0 ? `₹${Number(decision.recommended_amount).toLocaleString('en-IN')}` : 'N/A'],
                ].map(([k, v]) => (
                  <div key={k} className="bg-white rounded border p-3">
                    <p className="text-xs text-gray-500 uppercase mb-1">{k}</p>
                    <p className={`text-lg font-semibold ${k === 'Recommendation' ? (VERDICT_STYLE[v]?.split(' ')[2] || '') : ''}`}>{v ?? '—'}</p>
                  </div>
                ))}
              </div>
              <div className="flex gap-3 items-center">
                <a
                  href={downloadCAMUrl(caseId)}
                  download
                  className="inline-block px-4 py-2 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700 transition-colors"
                >
                  ⬇ Download CAM (.md)
                </a>
                <span className="text-xs text-gray-400">
                  {trace.rules_fired_count != null ? `${trace.rules_fired_count} rules evaluated` : ''}
                  {trace.schema_version && ` · schema ${trace.schema_version}`}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Run the appraisal to generate the CAM.</p>
          )}
        </div>
      )}

      {/* Tab: Judge (v3 only) */}
      {tab === 'judge' && isV3 && (
        <div className="space-y-5">
          {/* Evidence Quality Metrics */}
          {evidenceJudge && (
            <div className="bg-white rounded border px-4 py-4">
              <h3 className="font-medium text-sm text-gray-700 mb-3">Evidence Quality</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[['Accepted', evidenceJudge.accepted, 'text-green-600'],
                  ['Rejected', evidenceJudge.rejected, 'text-red-500'],
                  ['Precision@10', evidenceJudge.precision_at_10 != null ? (evidenceJudge.precision_at_10 * 100).toFixed(0) + '%' : '—', 'text-indigo-600'],
                  ['Corroboration', evidenceJudge.corroboration_rate != null ? (evidenceJudge.corroboration_rate * 100).toFixed(0) + '%' : '—', 'text-blue-600'],
                ].map(([label, val, color]) => (
                  <div key={label} className="text-center">
                    <p className={`text-2xl font-bold ${color}`}>{val ?? '—'}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                  </div>
                ))}
              </div>
              {evidenceJudge.fallback && <p className="text-xs text-amber-600 mt-2">⚠ Scored by heuristics (LLM model unavailable)</p>}
            </div>
          )}

          {/* Claim Graph */}
          {claimGraph && (
            <div className="bg-white rounded border px-4 py-4">
              <h3 className="font-medium text-sm text-gray-700 mb-1">Claim Graph</h3>
              <div className="flex gap-4 text-xs text-gray-500 mb-3">
                <span>Total: <strong>{claimGraph.claims_total}</strong></span>
                <span className="text-green-600">Corroborated: <strong>{claimGraph.corroborated}</strong></span>
                {claimGraph.contradictions > 0 && <span className="text-red-600">⚡ Contradictions: <strong>{claimGraph.contradictions}</strong></span>}
              </div>
              {claimGraph.claims?.length > 0 ? (
                <div className="space-y-1.5">
                  {claimGraph.claims.map(c => (
                    <div key={c.claim_id} className="flex items-start gap-2 text-sm py-1.5 border-b border-gray-100 last:border-0">
                      <span className={`mt-0.5 text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${
                        c.status === 'corroborated' ? 'bg-green-100 text-green-700' :
                        c.status === 'contradicted' ? 'bg-red-100 text-red-700' :
                        'bg-gray-100 text-gray-500'}`}>{c.status}</span>
                      <span className="text-gray-700 text-xs flex-1">{c.text}</span>
                      <span className="text-xs text-gray-400 shrink-0">conf {c.confidence?.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              ) : <p className="text-gray-400 text-sm">No claims extracted.</p>}
            </div>
          )}

          {/* Counterfactuals */}
          {counterfactuals?.scenarios?.length > 0 && (
            <div className="bg-white rounded border px-4 py-4">
              <h3 className="font-medium text-sm text-gray-700 mb-3">Counterfactual Scenarios</h3>
              <div className="space-y-2">
                {counterfactuals.scenarios.map(s => (
                  <div key={s.scenario_id} className="border rounded p-3 text-sm">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="font-medium text-gray-800">{s.description}</span>
                      <span className={`ml-auto text-xs font-bold px-2 py-0.5 rounded ${
                        s.hypothetical_recommendation === 'APPROVE' ? 'bg-green-100 text-green-700' :
                        s.hypothetical_recommendation === 'REJECT' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'}`}>
                        → {s.hypothetical_recommendation}
                      </span>
                    </div>
                    {s.rationale && <p className="text-xs text-gray-500 mt-1">{s.rationale}</p>}
                    <p className="text-xs text-gray-400 mt-1">Risk delta: {s.delta_risk_score > 0 ? '+' : ''}{(s.delta_risk_score * 100).toFixed(0)}%</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Search Plan */}
          {searchPlan && (
            <details className="bg-white rounded border px-4 py-3">
              <summary className="font-medium text-sm text-gray-700 cursor-pointer select-none">
                Research Plan ({searchPlan.query_count ?? searchPlan.queries?.length ?? 0} queries)
                {searchPlan.fallback && <span className="ml-2 text-xs text-amber-600">[deterministic fallback]</span>}
              </summary>
              <div className="mt-2 space-y-1">
                {searchPlan.queries?.map((q, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs py-1">
                    <span className={`shrink-0 px-1.5 py-0.5 rounded font-medium ${
                      q.priority === 1 ? 'bg-red-100 text-red-600' :
                      q.priority === 2 ? 'bg-yellow-100 text-yellow-600' :
                      'bg-gray-100 text-gray-500'}`}>{q.focus_area}</span>
                    <span className="text-gray-700">{q.query}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

