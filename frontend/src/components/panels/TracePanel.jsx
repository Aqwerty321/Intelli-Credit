import { useState } from 'react'
import { formatRiskScore, formatPercent, formatLabel, SEVERITY_BADGE } from '../../utils/formatters'
import RiskWaterfall from '../charts/RiskWaterfall'

function CollapsibleInputs({ inputs }) {
  const [open, setOpen] = useState(false)
  if (!inputs || !Object.keys(inputs).length) return null
  return (
    <div className="mt-1.5">
      <button onClick={() => setOpen(o => !o)} className="text-[11px] text-brand hover:underline">
        {open ? '▾ Hide inputs' : '▸ Show inputs'}
      </button>
      {open && (
        <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 bg-slate-50 rounded p-2 text-[11px] font-mono">
          {Object.entries(inputs).map(([k, v]) => (
            <div key={k} className="flex gap-1">
              <span className="text-slate-400">{k}:</span>
              <span className="text-slate-700">{JSON.stringify(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function TracePanel({ graphTrace, graphProbabilities, graphTopEntities, firings, minRiskPolicy, presentationMode, baseRisk = 0, llmTrace }) {
  return (
    <div className="space-y-3">
      {/* Graph trace */}
      {graphTrace && (
        <div className="bg-white border border-slate-200 rounded px-3 py-3">
          <h3 className="text-xs font-semibold text-slate-700 mb-2">Graph Analysis</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-2">
            {[
              ['Edges', graphTrace.edge_count ?? graphTrace.edges_examined ?? 0],
              ['Nodes', graphTrace.node_count ?? 0],
              ['Cycles', graphTrace.suspicious_cycles ?? 0, graphTrace.suspicious_cycles > 0 ? 'text-red-600 font-semibold' : ''],
              ['Label', graphTrace.gnn_label ? formatLabel(graphTrace.gnn_label) : 'clean'],
            ].map(([label, value, cls]) => (
              <div key={label} className="bg-slate-50 border border-slate-200 rounded px-2 py-1.5">
                <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{label}</p>
                <p className={`text-sm font-semibold text-slate-900 ${cls || ''}`}>{value}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            {graphTrace.no_graph_evidence && (
              <span className="bg-slate-50 border border-slate-200 text-slate-500 px-2 py-0.5 rounded">No suspicious circular flow</span>
            )}
            <span className="bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded">
              risk {formatRiskScore(graphTrace.gnn_risk_score)}
            </span>
            {graphTrace.fraud_alerts?.length > 0 && (
              <span className="bg-red-50 border border-red-300 text-red-700 px-2 py-0.5 rounded">
                🚨 {graphTrace.fraud_alerts.length} fraud alert{graphTrace.fraud_alerts.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          {graphProbabilities.length > 0 && (
            <div className="mt-3 grid gap-2 lg:grid-cols-3">
              {graphProbabilities.map(([label, probability]) => (
                <div key={label} className="rounded border border-slate-200 bg-slate-50 px-2 py-2">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span>{formatLabel(label)}</span>
                    <span className="font-mono">{formatPercent(probability * 100, 1)}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-brand"
                      style={{ width: `${Math.max(probability * 100, 4)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          {graphTopEntities.length > 0 && (
            <div className="mt-3">
              <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Top Entities</p>
              <div className="grid gap-2 md:grid-cols-2">
                {graphTopEntities.map(entity => (
                  <div key={entity.entity} className="rounded border border-slate-200 bg-slate-50 px-2 py-2">
                    <p className="text-xs font-medium text-slate-800">{entity.entity}</p>
                    <p className="text-[11px] text-slate-400">{entity.role || 'entity'} · score {formatRiskScore(entity.score)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {graphTrace.fraud_alerts?.length > 0 && (
            <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2">
              <p className="text-[11px] uppercase tracking-wider text-red-600 font-semibold mb-1">Fraud Alerts</p>
              <div className="space-y-1">
                {graphTrace.fraud_alerts.map((alert, idx) => (
                  <div key={`${alert.type}-${idx}`} className="rounded bg-white px-2 py-1.5 text-xs text-red-800">
                    {formatLabel(alert.type)} · {alert.severity} · {alert.entities?.join(', ')}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Risk waterfall chart */}
      {firings.length > 0 && <RiskWaterfall baseRisk={baseRisk} firings={firings} />}

      {/* Rule firings */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-2">
          Rule Firings <span className="text-[11px] text-slate-400 font-normal">({firings.length})</span>
        </h2>
        {!firings.length ? (
          <p className="text-slate-400 text-xs italic">No rules triggered — all thresholds within safe limits.</p>
        ) : (
          <div className="bg-white border border-slate-200 rounded divide-y divide-slate-100">
            {firings.map((rf, i) => (
              <div key={i} className="px-3 py-2">
                <div className="flex flex-wrap gap-1.5 items-center mb-0.5">
                  <span className="font-mono text-[11px] text-slate-400">#{rf.rule_id}</span>
                  <span className="font-medium text-xs text-slate-800">{rf.rule_slug}</span>
                  <span className={`text-[11px] px-1.5 py-0.5 rounded font-semibold ${SEVERITY_BADGE[rf.severity] || 'bg-slate-100 text-slate-600'}`}>
                    {rf.severity}
                  </span>
                  <span className="text-[11px] font-mono text-orange-600 font-semibold">+{formatRiskScore(rf.risk_adjustment)}</span>
                  {rf.hard_reject && <span className="text-[11px] bg-red-600 text-white px-1.5 py-0.5 rounded font-bold">HARD REJECT</span>}
                </div>
                <p className="text-xs text-slate-600">{rf.rationale}</p>
                {rf.missing_data_flags?.length > 0 && !presentationMode && (
                  <p className="text-[11px] text-amber-600 mt-1 bg-amber-50 px-2 py-0.5 rounded">
                    ⚠ Missing: {rf.missing_data_flags.join(', ')}
                  </p>
                )}
                <CollapsibleInputs inputs={rf.inputs} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Conservative defaults */}
      {minRiskPolicy.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded px-3 py-2">
          <h3 className="text-xs font-semibold text-amber-800 mb-1">Conservative Defaults ({minRiskPolicy.length})</h3>
          <p className="text-[11px] text-amber-700 mb-1.5">Fields not found in documents — conservative defaults applied.</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            {minRiskPolicy.map((p, i) => (
              <div key={i} className="flex justify-between text-[11px]">
                <span className="font-mono text-amber-700">{p.field}</span>
                <span className="text-amber-600">→ {JSON.stringify(p.default_value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LLM Risk Assessment */}
      {llmTrace && llmTrace.answer && (
        <div className="bg-white border border-slate-200 rounded px-3 py-3">
          <h3 className="text-xs font-semibold text-slate-700 mb-2">LLM Risk Assessment</h3>
          <div className="flex gap-2 text-[11px] text-slate-400 mb-2">
            <span className="bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded font-mono">{llmTrace.model}</span>
            <span>{llmTrace.tokens_used} tokens</span>
            <span>{(llmTrace.latency_ms / 1000).toFixed(1)}s</span>
          </div>
          {llmTrace.thinking && (
            <details className="mb-2">
              <summary className="text-[11px] text-brand cursor-pointer hover:underline">Show reasoning chain</summary>
              <pre className="mt-1 text-[11px] text-slate-600 bg-slate-50 rounded p-2 whitespace-pre-wrap max-h-60 overflow-y-auto">{llmTrace.thinking}</pre>
            </details>
          )}
          <pre className="text-[11px] text-slate-700 bg-slate-50 rounded p-2 whitespace-pre-wrap max-h-40 overflow-y-auto">{llmTrace.answer}</pre>
        </div>
      )}
    </div>
  )
}
