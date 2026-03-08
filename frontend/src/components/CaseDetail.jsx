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

const SEVERITY_BADGE = { HIGH: 'bg-red-100 text-red-700', MEDIUM: 'bg-yellow-100 text-yellow-700', LOW: 'bg-blue-100 text-blue-700', CRITICAL: 'bg-red-200 text-red-900' }

export default function CaseDetail() {
  const { caseId } = useParams()
  const [caseData, setCaseData] = useState(null)
  const [tab, setTab] = useState('documents')
  const [uploading, setUploading] = useState(false)
  const [running, setRunning] = useState(false)
  const [log, setLog] = useState([])
  const logRef = useRef(null)
  const fileRef = useRef(null)

  const reload = () => fetch(`/api/cases/${caseId}`).then(r => r.json()).then(setCaseData)

  useEffect(() => { reload() }, [caseId])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log])

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
    setRunning(true)
    setLog([])
    setTab('run')
    const es = new EventSource(`/api/run/${caseId}/stream`)
    es.addEventListener('progress', e => setLog(l => [...l, JSON.parse(e.data)]))
    es.addEventListener('research_complete', e => setLog(l => [...l, { phase: 'research', ...JSON.parse(e.data) }]))
    es.addEventListener('warning', e => setLog(l => [...l, { phase: 'warning', ...JSON.parse(e.data) }]))
    es.addEventListener('complete', e => {
      setLog(l => [...l, { phase: 'DONE', ...JSON.parse(e.data) }])
      setRunning(false)
      es.close()
      reload()
    })
    es.addEventListener('error', e => {
      setLog(l => [...l, { phase: 'ERROR', message: e.data }])
      setRunning(false)
      es.close()
    })
  }

  if (!caseData) return <p className="text-gray-500 py-10 text-center">Loading…</p>

  const trace = caseData.trace || {}
  const decision = trace.decision || {}
  const firings = trace.rule_firings || []
  const research = caseData.research || {}

  const tabs = ['documents', 'run', 'evidence', 'trace', 'cam']

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{caseData.company_name}</h1>
        <p className="text-gray-500 text-sm mt-1">
          ₹{Number(caseData.loan_amount).toLocaleString('en-IN')} · {caseData.loan_purpose}
          {caseData.sector && ` · ${caseData.sector}`}
          {caseData.location && `, ${caseData.location}`}
        </p>
      </div>

      {/* Verdict banner */}
      {decision.recommendation && (
        <div className={`rounded-lg border-l-4 p-4 mb-6 ${VERDICT_STYLE[decision.recommendation] || ''}`}>
          <div className="flex items-center gap-4">
            <span className="text-2xl font-bold">{decision.recommendation}</span>
            <span className={`text-xl font-mono font-semibold ${RISK_COLOR(decision.risk_score)}`}>
              Risk: {decision.risk_score?.toFixed(2)}
            </span>
            {decision.recommended_amount > 0 && (
              <span className="text-sm">Sanction: ₹{Number(decision.recommended_amount).toLocaleString('en-IN')}</span>
            )}
          </div>
        </div>
      )}

      {/* Run button */}
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={handleRun}
          disabled={running || !caseData.documents?.length}
          className="px-4 py-2 bg-brand text-white text-sm rounded font-medium hover:bg-brand-dark disabled:opacity-40 transition-colors"
        >
          {running ? '⏳ Running…' : '▶ Run Appraisal'}
        </button>
        {!caseData.documents?.length && <span className="text-xs text-gray-400">Upload documents first</span>}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="flex gap-1">
          {tabs.map(t => (
            <button key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-sm font-medium rounded-t transition-colors capitalize
                ${tab === t ? 'bg-white border border-b-white text-brand -mb-px' : 'text-gray-500 hover:text-gray-700'}`}>
              {t}
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

          <label className={`inline-flex items-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm cursor-pointer ${uploading ? 'opacity-50' : ''}`}>
            <input ref={fileRef} type="file" accept=".pdf,.json,.txt,.md" className="hidden" onChange={handleUpload} disabled={uploading} />
            {uploading ? 'Uploading…' : '+ Upload document'}
          </label>
        </div>
      )}

      {/* Tab: Run log */}
      {tab === 'run' && (
        <div>
          <h2 className="font-medium mb-3">Pipeline Log</h2>
          <div ref={logRef} className="bg-gray-900 text-green-300 rounded p-4 h-64 overflow-y-auto font-mono text-xs">
            {log.length === 0 && <span className="text-gray-500">Click "Run Appraisal" to start…</span>}
            {log.map((l, i) => (
              <div key={i} className={`${l.phase === 'ERROR' ? 'text-red-400' : l.phase === 'DONE' ? 'text-yellow-300 font-bold' : ''}`}>
                [{l.phase?.toUpperCase()}] {l.message || JSON.stringify(l)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Evidence (research findings) */}
      {tab === 'evidence' && (
        <div>
          <h2 className="font-medium mb-3">Research Evidence <span className="text-xs text-gray-400">({(research.findings || []).length} findings)</span></h2>
          {!(research.findings?.length) ? (
            <p className="text-gray-400 text-sm">Run the appraisal to collect research evidence.</p>
          ) : (
            <div className="space-y-3">
              {research.findings.map((f, i) => (
                <div key={i} className={`bg-white rounded border-l-4 px-4 py-3 ${f.risk_impact === 'negative' ? 'border-red-400' : f.risk_impact === 'positive' ? 'border-green-400' : 'border-gray-300'}`}>
                  <div className="flex gap-2 items-start">
                    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded uppercase ${f.risk_impact === 'negative' ? 'bg-red-100 text-red-700' : f.risk_impact === 'positive' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {f.risk_impact}
                    </span>
                    <span className="text-xs text-gray-500 uppercase">{f.category}</span>
                    <span className="ml-auto text-xs text-gray-400">conf: {f.confidence?.toFixed(2)}</span>
                  </div>
                  <p className="text-sm mt-2">{f.summary}</p>
                  <a href={f.source} target="_blank" rel="noreferrer" className="text-xs text-blue-500 hover:underline mt-1 block truncate">{f.source}</a>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Trace (rule firings) */}
      {tab === 'trace' && (
        <div>
          <h2 className="font-medium mb-3">Rule Firings <span className="text-xs text-gray-400">({firings.length} rules fired)</span></h2>
          {!firings.length ? (
            <p className="text-gray-400 text-sm">Run the appraisal first.</p>
          ) : (
            <div className="space-y-3">
              {firings.map((rf, i) => (
                <div key={i} className="bg-white rounded border px-4 py-3">
                  <div className="flex gap-3 items-center mb-1">
                    <span className="font-mono text-xs text-gray-400">#{rf.rule_id}</span>
                    <span className="font-medium text-sm">{rf.rule_slug}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ml-auto ${SEVERITY_BADGE[rf.severity] || 'bg-gray-100 text-gray-600'}`}>{rf.severity}</span>
                    <span className="text-xs font-mono text-orange-600">+{rf.risk_adjustment?.toFixed(2)}</span>
                    {rf.hard_reject && <span className="text-xs bg-red-600 text-white px-1.5 py-0.5 rounded">HARD REJECT</span>}
                  </div>
                  <p className="text-sm text-gray-700">{rf.rationale}</p>
                  {rf.missing_data_flags?.length > 0 && (
                    <p className="text-xs text-amber-600 mt-1">⚠ Missing data: {rf.missing_data_flags.join(', ')}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: CAM download */}
      {tab === 'cam' && (
        <div>
          <h2 className="font-medium mb-3">Credit Appraisal Memo</h2>
          {decision.recommendation ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                {[
                  ['Recommendation', decision.recommendation],
                  ['Risk Score', decision.risk_score?.toFixed(2)],
                  ['Sanction Amount', decision.recommended_amount ? `₹${Number(decision.recommended_amount).toLocaleString('en-IN')}` : 'N/A'],
                ].map(([k, v]) => (
                  <div key={k} className="bg-white rounded border p-3">
                    <p className="text-xs text-gray-500 uppercase mb-1">{k}</p>
                    <p className="text-lg font-semibold">{v ?? '—'}</p>
                  </div>
                ))}
              </div>
              <a
                href={`/api/cases/${caseId}/cam`}
                download
                className="inline-block px-4 py-2 bg-brand text-white rounded text-sm hover:bg-brand-dark"
              >
                ⬇ Download CAM
              </a>
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Run the appraisal to generate the CAM.</p>
          )}
        </div>
      )}
    </div>
  )
}
