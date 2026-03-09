import { formatRiskScore, formatPercent, asNumber } from '../../utils/formatters'
import CounterfactualBar from '../charts/CounterfactualBar'

export default function JudgePanel({ evidenceJudge, claimGraph, counterfactuals, searchPlan, presentationMode }) {
  return (
    <div className="space-y-3">
      {/* Evidence Quality */}
      {evidenceJudge && (
        <div className="bg-white rounded border border-slate-200 px-3 py-3">
          <h3 className="text-xs font-semibold text-slate-700 mb-2">Evidence Quality</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              ['Accepted', evidenceJudge.accepted, 'text-green-600'],
              ['Rejected', evidenceJudge.rejected, 'text-red-500'],
              ['Precision@10', evidenceJudge.precision_at_10 != null ? formatPercent(evidenceJudge.precision_at_10 * 100, 0) : '—', 'text-brand'],
              ['Corroboration', evidenceJudge.corroboration_rate != null ? formatPercent(evidenceJudge.corroboration_rate * 100, 0) : '—', 'text-blue-600'],
            ].map(([label, val, color]) => (
              <div key={label} className="bg-slate-50 border border-slate-200 rounded px-2 py-2">
                <p className={`text-lg font-bold ${color}`}>{val ?? '—'}</p>
                <p className="text-[11px] text-slate-500">{label}</p>
              </div>
            ))}
          </div>
          {evidenceJudge.fallback && !presentationMode && (
            <p className="text-[11px] text-amber-600 mt-2">⚠ Scored by heuristics (LLM unavailable)</p>
          )}
        </div>
      )}

      {/* Claim Graph */}
      {claimGraph && (
        <div className="bg-white rounded border border-slate-200 px-3 py-3">
          <h3 className="text-xs font-semibold text-slate-700 mb-1">Claim Graph</h3>
          <div className="flex gap-3 text-[11px] text-slate-500 mb-2">
            <span>Total: <strong>{claimGraph.claims_total}</strong></span>
            <span className="text-green-600">Corroborated: <strong>{claimGraph.corroborated}</strong></span>
            {claimGraph.contradictions > 0 && <span className="text-red-600">⚡ Contradictions: <strong>{claimGraph.contradictions}</strong></span>}
          </div>
          {claimGraph.claims?.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {claimGraph.claims.map(c => (
                <div key={c.claim_id} className="flex items-start gap-2 text-xs py-1.5">
                  <span className={`mt-0.5 text-[11px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
                    c.status === 'corroborated' ? 'bg-green-100 text-green-700' :
                    c.status === 'contradicted' ? 'bg-red-100 text-red-700' :
                    'bg-slate-100 text-slate-500'}`}>{c.status}</span>
                  <span className="text-slate-700 text-[11px] flex-1">{c.text}</span>
                  <span className="text-[11px] text-slate-400 shrink-0 font-mono">{formatRiskScore(c.confidence)}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-slate-400 text-xs">No claims extracted.</p>}
        </div>
      )}

      {/* Counterfactuals */}
      {counterfactuals?.scenarios?.length > 0 && (
        <>
          <CounterfactualBar scenarios={counterfactuals.scenarios} />
          <div className="bg-white rounded border border-slate-200 px-3 py-3">
            <h3 className="text-xs font-semibold text-slate-700 mb-2">Counterfactual Scenarios</h3>
          <div className="divide-y divide-slate-100">
            {counterfactuals.scenarios.map(s => (
              <div key={s.scenario_id} className="py-2">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-medium text-slate-800">{s.description}</span>
                  <span className={`ml-auto text-[11px] font-bold px-1.5 py-0.5 rounded ${
                    s.hypothetical_recommendation === 'APPROVE' ? 'bg-green-100 text-green-700' :
                    s.hypothetical_recommendation === 'REJECT' ? 'bg-red-100 text-red-700' :
                    'bg-amber-100 text-amber-700'}`}>
                    → {s.hypothetical_recommendation}
                  </span>
                </div>
                {s.rationale && <p className="text-[11px] text-slate-500">{s.rationale}</p>}
                <p className="text-[11px] text-slate-400">Δ risk: {asNumber(s.delta_risk_score) > 0 ? '+' : ''}{formatPercent((asNumber(s.delta_risk_score) || 0) * 100, 0)}</p>
              </div>
            ))}
          </div>
        </div>
        </>
      )}

      {/* Search Plan */}
      {searchPlan && (
        <details className="bg-white rounded border border-slate-200 px-3 py-2">
          <summary className="text-xs font-semibold text-slate-700 cursor-pointer select-none">
            Research Plan ({searchPlan.query_count ?? searchPlan.queries?.length ?? 0} queries)
            {searchPlan.fallback && !presentationMode && <span className="ml-2 text-[11px] text-amber-600">[deterministic fallback]</span>}
          </summary>
          <div className="mt-1.5 space-y-1">
            {searchPlan.queries?.map((q, i) => (
              <div key={i} className="flex items-start gap-2 text-[11px] py-0.5">
                <span className={`shrink-0 px-1.5 py-0.5 rounded font-medium ${
                  q.priority === 1 ? 'bg-red-100 text-red-600' :
                  q.priority === 2 ? 'bg-amber-100 text-amber-600' :
                  'bg-slate-100 text-slate-500'}`}>{q.focus_area}</span>
                <span className="text-slate-700">{q.query}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
