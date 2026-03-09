import PipelineTimeline from './PipelineTimeline'
import { formatRiskScore } from '../../utils/formatters'

export default function RunPanel({
  log, logRef, running, sseError,
  syncResult, runningSync, syncError,
  onSyncRun, onDismissSync,
  hasRun, trace,
  onRun, caseData,
  presentationMode,
}) {
  return (
    <div>
      {/* Run buttons */}
      {!presentationMode && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            onClick={onRun}
            disabled={running || runningSync || !caseData.documents?.length}
            className="px-3 py-1.5 bg-brand text-white text-xs rounded font-medium hover:bg-brand-dark disabled:opacity-40"
          >
            {running ? '⏳ Running…' : hasRun ? '↺ Re-run' : '▶ Run Appraisal'}
          </button>
          <button
            onClick={onSyncRun}
            disabled={running || runningSync || !caseData.documents?.length}
            className="px-3 py-1.5 bg-slate-700 text-white text-xs rounded font-medium hover:bg-slate-800 disabled:opacity-40"
            title="Blocking synchronous run"
          >
            {runningSync ? '⏳ Sync…' : 'Sync'}
          </button>
          {!caseData.documents?.length && <span className="text-[11px] text-slate-400">Upload documents first</span>}
          {syncError && <span className="text-[11px] text-red-600">⚠ {syncError}</span>}
          {hasRun && !running && !runningSync && (
            <span className="text-[11px] text-slate-400">Last: {trace?.timestamp ? new Date(trace.timestamp).toLocaleString() : 'unknown'}</span>
          )}
        </div>
      )}

      {/* Sync result banner */}
      {syncResult && !running && !presentationMode && (
        <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2 mb-3 text-xs flex items-center gap-2">
          <span className="font-medium text-blue-700">Sync complete:</span>
          <span className={`font-semibold ${syncResult.recommendation === 'APPROVE' ? 'text-green-700' : syncResult.recommendation === 'CONDITIONAL' ? 'text-amber-700' : 'text-red-700'}`}>
            {syncResult.recommendation}
          </span>
          <span className="text-slate-500">Risk: {formatRiskScore(syncResult.risk_score)}</span>
          <button onClick={onDismissSync} className="ml-auto text-slate-400 hover:text-slate-600 text-[11px]">✕</button>
        </div>
      )}

      <PipelineTimeline log={log} />

      <h2 className="text-sm font-semibold text-slate-700 mb-2">Pipeline Log</h2>
      <div
        ref={logRef}
        className="bg-slate-950 text-green-300 rounded p-3 h-56 overflow-y-auto font-mono text-[11px] space-y-0.5"
      >
        {log.length === 0 && <span className="text-slate-500">Click "Run Appraisal" to start…</span>}
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
      {running && <p className="text-[11px] text-slate-400 mt-1.5">Pipeline running…</p>}
      {sseError && (
        <div className="mt-2 flex items-center gap-2 text-xs bg-amber-50 border border-amber-200 rounded px-3 py-1.5">
          <span className="text-amber-700">⚠ Stream failed — try sync fallback?</span>
          <button
            onClick={onSyncRun}
            disabled={runningSync}
            className="px-2 py-1 bg-slate-700 text-white rounded text-[11px] hover:bg-slate-800 disabled:opacity-40"
          >
            {runningSync ? '⏳' : 'Run Sync'}
          </button>
        </div>
      )}
    </div>
  )
}
