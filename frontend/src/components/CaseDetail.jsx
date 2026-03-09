import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
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
  checkFactsExist,
  autofetchStreamUrl,
} from '../services/api'
import {
  asNumber,
  formatRiskScore,
  formatPercent,
  formatCurrency,
  formatLabel,
  uniqueLines,
  EMPTY_NOTE_FORM,
} from '../utils/formatters'

import CaseHeader from './panels/CaseHeader'
import KPIStrip from './panels/KPIStrip'
import DocumentsPanel from './panels/DocumentsPanel'
import RunPanel from './panels/RunPanel'
import NotesPanel from './panels/NotesPanel'
import EvidencePanel from './panels/EvidencePanel'
import TracePanel from './panels/TracePanel'
import CAMPanel from './panels/CAMPanel'
import JudgePanel from './panels/JudgePanel'
import GraphPanel from './panels/GraphPanel'
import ConfirmModal from './ConfirmModal'

export default function CaseDetail() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const presentationMode = new URLSearchParams(location.search).get('presentation') === '1' || import.meta.env.VITE_PRESENTATION_MODE === '1'

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

  // AutoFetch
  const [autoFetching, setAutoFetching] = useState(false)
  const [autoFetchLog, setAutoFetchLog] = useState([])
  const [showOverwriteConfirm, setShowOverwriteConfirm] = useState(false)
  const autoFetchEsRef = useRef(null)

  const reload = useCallback(() =>
    getCase(caseId).then(setCaseData).catch(() => {}), [caseId])

  const reloadNotes = useCallback(() => {
    setNotesLoading(true)
    listNotes(caseId).then(ns => { setNotesList(ns); setNotesLoading(false) }).catch(() => setNotesLoading(false))
  }, [caseId])

  useEffect(() => { reload() }, [reload])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log])
  useEffect(() => { if (tab === 'notes') reloadNotes() }, [tab, reloadNotes])
  useEffect(() => () => { if (esRef.current) { esRef.current.close(); esRef.current = null } }, [])
  useEffect(() => () => { if (autoFetchEsRef.current) { autoFetchEsRef.current.close(); autoFetchEsRef.current = null } }, [])
  useEffect(() => {
    if (presentationMode && tab === 'documents') setTab('trace')
  }, [presentationMode, tab])

  // ── Handlers ──────────────────────────────────────────────────────────────

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

  const startAutoFetch = (force = false) => {
    if (autoFetchEsRef.current) { autoFetchEsRef.current.close(); autoFetchEsRef.current = null }
    setAutoFetching(true)
    setAutoFetchLog([])
    setTab('documents')
    const es = new EventSource(autofetchStreamUrl(caseId, force))
    autoFetchEsRef.current = es
    const addLog = (data) => setAutoFetchLog(l => [...l, data])
    es.addEventListener('progress', e => addLog(JSON.parse(e.data)))
    es.addEventListener('research_complete', e => addLog({ phase: 'research_complete', ...JSON.parse(e.data) }))
    es.addEventListener('complete', e => {
      addLog({ phase: 'DONE', ...JSON.parse(e.data) })
      setAutoFetching(false)
      es.close(); autoFetchEsRef.current = null
      reload()
    })
    es.addEventListener('error', e => {
      const data = typeof e.data === 'string' ? e.data : 'Connection error'
      addLog({ phase: 'ERROR', message: data })
      setAutoFetching(false)
      es.close(); autoFetchEsRef.current = null
    })
  }

  const handleAutoFetch = async () => {
    try {
      const { facts_exists } = await checkFactsExist(caseId)
      if (facts_exists) {
        setShowOverwriteConfirm(true)
      } else {
        startAutoFetch(false)
      }
    } catch {
      startAutoFetch(false)
    }
  }

  const handleOverwriteConfirm = () => {
    setShowOverwriteConfirm(false)
    startAutoFetch(true)
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

  // ── Derived data ──────────────────────────────────────────────────────────

  if (!caseData) return <p className="text-slate-400 py-10 text-center text-sm">Loading…</p>

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

  const graphProbabilities = Object.entries(graphTrace?.class_probabilities || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
  const graphTopEntities = graphTrace?.top_entities || []

  const tabs = presentationMode
    ? ['evidence', 'trace', ...(hasRun && graphTrace?.visual_ready ? ['graph'] : []), 'cam', ...(hasRun && isV3 ? ['judge'] : [])]
    : ['documents', 'run', 'notes', 'evidence', 'trace', ...(hasRun && graphTrace?.visual_ready ? ['graph'] : []), 'cam', ...(hasRun && isV3 ? ['judge'] : [])]

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div>
      <CaseHeader
        caseData={caseData}
        hasRun={hasRun}
        decision={decision}
        firings={firings}
        findings={findings}
        showDeleteCase={showDeleteCase}
        setShowDeleteCase={setShowDeleteCase}
        onDeleteCase={handleDeleteCase}
        presentationMode={presentationMode}
      />

      {hasRun && (
        <KPIStrip
          decision={decision}
          firings={firings}
          findings={findings}
          research={research}
          evidenceJudge={evidenceJudge}
          graphTrace={graphTrace}
        />
      )}

      {/* Tab navigation */}
      <div className="border-b border-slate-200 mb-4">
        <nav className="flex gap-0 flex-wrap">
          {tabs.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-xs font-medium capitalize border-b-2 transition-colors ${
                tab === t
                  ? 'text-brand border-brand'
                  : 'text-slate-500 border-transparent hover:text-slate-700'
              }`}
            >
              {t}
              {t === 'trace' && firings.length > 0 && <span className="ml-1 bg-slate-100 text-slate-600 text-[11px] rounded-full px-1.5">{firings.length}</span>}
              {t === 'evidence' && findings.length > 0 && <span className="ml-1 bg-slate-100 text-slate-600 text-[11px] rounded-full px-1.5">{findings.length}</span>}
              {t === 'notes' && notesList.length > 0 && <span className="ml-1 bg-slate-100 text-slate-600 text-[11px] rounded-full px-1.5">{notesList.length}</span>}
            </button>
          ))}
        </nav>
      </div>

      {/* Panel content */}
      {tab === 'documents' && (
        <>
          <DocumentsPanel
            documents={caseData.documents} uploading={uploading} fileRef={fileRef} onUpload={handleUpload}
            onAutoFetch={presentationMode ? undefined : handleAutoFetch}
            autoFetching={autoFetching}
          />
          {autoFetchLog.length > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-semibold text-slate-700 mb-2">AutoFetch Log</h3>
              <div className="bg-slate-950 text-green-300 rounded p-3 h-44 overflow-y-auto font-mono text-[11px] space-y-0.5">
                {autoFetchLog.map((l, i) => (
                  <div key={i} className={l.phase === 'ERROR' ? 'text-red-400' : l.phase === 'DONE' ? 'text-blue-300' : ''}>
                    {l.phase === 'DONE' ? `✓ AutoFetch complete — ${l.filename} (${l.findings_count} findings, ${l.generation_method})` :
                     l.phase === 'ERROR' ? `✗ ${l.message || 'AutoFetch failed'}` :
                     l.phase === 'research_complete' ? `◆ Research done: ${l.findings_count} findings (${l.negative_count} negative)` :
                     `▸ ${l.message || JSON.stringify(l)}`}
                  </div>
                ))}
              </div>
            </div>
          )}
          <ConfirmModal
            open={showOverwriteConfirm}
            title="Overwrite facts.md?"
            message="A facts.md document already exists for this case. AutoFetch will overwrite it with fresh research data."
            confirmLabel="Overwrite"
            danger
            onConfirm={handleOverwriteConfirm}
            onCancel={() => setShowOverwriteConfirm(false)}
          />
        </>
      )}

      {tab === 'run' && (
        <RunPanel
          log={log} logRef={logRef} running={running} sseError={sseError}
          syncResult={syncResult} runningSync={runningSync} syncError={syncError}
          onSyncRun={handleSyncRun} onDismissSync={() => setSyncResult(null)}
          hasRun={hasRun} trace={trace}
          onRun={handleRun} caseData={caseData}
          presentationMode={presentationMode}
        />
      )}

      {tab === 'notes' && (
        <NotesPanel
          caseId={caseId}
          notesList={notesList}
          notesLoading={notesLoading}
          noteFilter={noteFilter}
          setNoteFilter={setNoteFilter}
          noteForm={noteForm}
          setNoteForm={setNoteForm}
          noteEditId={noteEditId}
          setNoteEditId={setNoteEditId}
          noteSubmitting={noteSubmitting}
          noteDeleteId={noteDeleteId}
          setNoteDeleteId={setNoteDeleteId}
          onNoteSubmit={handleNoteSubmit}
          onNoteEdit={handleNoteEdit}
          onNoteDelete={handleNoteDelete}
          toggleTagFilter={toggleTagFilter}
        />
      )}

      {tab === 'evidence' && (
        <EvidencePanel findings={findings} research={research} />
      )}

      {tab === 'trace' && (
        <TracePanel
          graphTrace={graphTrace}
          graphProbabilities={graphProbabilities}
          graphTopEntities={graphTopEntities}
          firings={firings}
          minRiskPolicy={minRiskPolicy}
          presentationMode={presentationMode}
          baseRisk={trace.orchestration_impact?.pre_orchestration_risk_score ?? 0}
        />
      )}

      {tab === 'cam' && (
        <CAMPanel caseId={caseId} decision={decision} trace={trace} hasRun={hasRun} />
      )}

      {tab === 'graph' && (
        <GraphPanel caseId={caseId} graphTrace={graphTrace} />
      )}

      {tab === 'judge' && isV3 && (
        <JudgePanel
          evidenceJudge={evidenceJudge}
          claimGraph={claimGraph}
          counterfactuals={counterfactuals}
          searchPlan={searchPlan}
          presentationMode={presentationMode}
        />
      )}
    </div>
  )
}
