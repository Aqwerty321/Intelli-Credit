import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'

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

export default function CaseDetail() {
  const { caseId } = useParams()
  const [caseData, setCaseData] = useState(null)
  const [tab, setTab] = useState('documents')
  const [uploading, setUploading] = useState(false)
  const [running, setRunning] = useState(false)
  const [log, setLog] = useState([])
  const logRef = useRef(null)
  const fileRef = useRef(null)
  const esRef = useRef(null)

  const reload = () => fetch(`/api/cases/${caseId}`).then(r => r.json()).then(setCaseData)

  useEffect(() => { reload() }, [caseId])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log])
  // Clean up SSE on unmount
  useEffect(() => () => { if (esRef.current) { esRef.current.close(); esRef.current = null } }, [])

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    await fetch(`/api/cases/${caseId}/documents`, { method: 'POST', body: fd })
    await reload()
    setUploading(false)
  }

  const handleRun = () => {
    // Close any existing stream before starting a new one
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    setRunning(true)
    setLog([])
    setTab('run')
    const es = new EventSource(`/api/run/${caseId}/stream`)
    esRef.current = es
    es.addEventListener('progress', e => setLog(l => [...l, JSON.parse(e.data)]))
    es.addEventListener('research_complete', e => setLog(l => [...l, { phase: 'research_complete', ...JSON.parse(e.data) }]))
    es.addEventListener('warning', e => setLog(l => [...l, { phase: 'warning', ...JSON.parse(e.data) }]))
    es.addEventListener('complete', e => {
      setLog(l => [...l, { phase: 'DONE', ...JSON.parse(e.data) }])
      setRunning(false)
      es.close()
      esRef.current = null
      reload()
    })
    es.addEventListener('error', e => {
      setLog(l => [...l, { phase: 'ERROR', message: typeof e.data === 'string' ? e.data : 'Connection error' }])
      setRunning(false)
      es.close()
      esRef.current = null
    })
  }

  if (!caseData) return <p className="text-gray-500 py-10 text-center">Loading…</p>

  const trace = caseData.trace || {}
  const decision = trace.decision || {}
  const firings = trace.rule_firings || []
  const minRiskPolicy = trace.minimum_risk_policy || []
  const graphTrace = trace.graph_trace || null
  const research = caseData.research || {}
  const findings = research.findings || []

  const tabs = ['documents', 'run', 'evidence', 'trace', 'cam']
  const hasRun = !!decision.recommendation

  return (
    <div>
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-semibold">{caseData.company_name}</h1>
        <p className="text-gray-500 text-sm mt-1">
          ₹{Number(caseData.loan_amount).toLocaleString('en-IN')} · {caseData.loan_purpose}
          {caseData.sector && ` · ${caseData.sector}`}
          {caseData.location && `, ${caseData.location}`}
        </p>
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

      {/* Run / Re-run button */}
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={handleRun}
          disabled={running || !caseData.documents?.length}
          className="px-4 py-2 bg-indigo-600 text-white text-sm rounded font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors"
        >
          {running ? '⏳ Running…' : hasRun ? '↺ Re-run Appraisal' : '▶ Run Appraisal'}
        </button>
        {!caseData.documents?.length && <span className="text-xs text-gray-400">Upload documents first</span>}
        {hasRun && !running && (
          <span className="text-xs text-gray-400">Last run: {trace.timestamp ? new Date(trace.timestamp).toLocaleString() : 'unknown'}</span>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="flex gap-1">
          {tabs.map(t => (
            <button key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium rounded-t transition-colors capitalize
                ${tab === t ? 'bg-white border border-b-white text-indigo-600 -mb-px' : 'text-gray-500 hover:text-gray-700'}`}>
              {t}
              {t === 'trace' && firings.length > 0 && <span className="ml-1 text-xs bg-indigo-100 text-indigo-600 px-1 rounded">{firings.length}</span>}
              {t === 'evidence' && findings.length > 0 && <span className="ml-1 text-xs bg-gray-100 text-gray-500 px-1 rounded">{findings.length}</span>}
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
                  href={`/api/cases/${caseId}/cam`}
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
    </div>
  )
}

