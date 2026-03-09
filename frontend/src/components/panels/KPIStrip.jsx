import {
  formatRiskScore,
  formatPercent,
  formatLabel,
  riskBand,
  asNumber,
  VERDICT_DOT,
  VERDICT_TEXT,
} from '../../utils/formatters'
import RiskGauge from '../charts/RiskGauge'

export default function KPIStrip({ decision, firings, findings, research, evidenceJudge, graphTrace }) {
  const tiles = [
    {
      label: 'Verdict',
      value: decision.recommendation || 'Pending',
      dotClass: VERDICT_DOT[decision.recommendation],
      valueClass: VERDICT_TEXT[decision.recommendation] || 'text-slate-500',
    },
    {
      label: 'Risk Score',
      value: formatRiskScore(decision.risk_score),
      sub: riskBand(decision.risk_score),
      gauge: asNumber(decision.risk_score),
    },
    {
      label: 'Rules Fired',
      value: firings.length,
      sub: firings.length > 0 ? `+${formatRiskScore(firings.reduce((s, r) => s + (Number(r.risk_adjustment) || 0), 0))} adj` : 'Clean',
    },
    {
      label: 'Evidence',
      value: evidenceJudge?.accepted != null ? `${evidenceJudge.accepted}/${findings.length || evidenceJudge.accepted}` : `${findings.length}`,
      sub: evidenceJudge?.precision_at_10 != null
        ? `P@10: ${formatPercent(evidenceJudge.precision_at_10 * 100, 0)}`
        : `${research.corroborated_findings ?? 0} corroborated`,
    },
    {
      label: 'Graph',
      value: graphTrace?.evidence_source === 'synthesized_from_facts'
        ? 'Synthesized'
        : formatLabel(graphTrace?.gnn_label),
      sub: graphTrace
        ? `${graphTrace.node_count ?? 0}n · ${graphTrace.edge_count ?? graphTrace.edges_examined ?? 0}e · ${graphTrace.suspicious_cycles ?? 0} cycles`
        : 'No graph data',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
      {tiles.map(t => (
        <div key={t.label} className="bg-white border border-slate-200 rounded px-3 py-2">
          <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{t.label}</p>
          {t.gauge != null ? (
            <div className="flex items-center gap-2 mt-0.5">
              <RiskGauge riskScore={t.gauge} size={48} />
              <div>
                <p className={`text-lg font-semibold leading-tight ${t.valueClass || 'text-slate-900'}`}>{t.value}</p>
                {t.sub && <p className="text-[11px] text-slate-400">{t.sub}</p>}
              </div>
            </div>
          ) : (
            <>
              <p className={`text-lg font-semibold mt-0.5 leading-tight ${t.valueClass || 'text-slate-900'}`}>
                {t.dotClass && <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${t.dotClass}`} />}
                {t.value}
              </p>
              {t.sub && <p className="text-[11px] text-slate-400 mt-0.5">{t.sub}</p>}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
