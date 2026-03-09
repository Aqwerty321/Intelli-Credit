import { formatRiskScore, IMPACT_STYLE, SOURCE_TIER_BADGE } from '../../utils/formatters'
import EvidenceScatter from '../charts/EvidenceScatter'

export default function EvidencePanel({ findings, research }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-slate-700">
          Research Evidence <span className="text-[11px] text-slate-400 font-normal">({findings.length})</span>
        </h2>
        {research.corroborated_findings != null && (
          <span className="text-[11px] text-slate-500">
            {research.corroborated_findings} corroborated · {findings.length - research.corroborated_findings} need more
          </span>
        )}
      </div>
      {!findings.length ? (
        <p className="text-slate-400 text-xs">Run the appraisal to collect research evidence.</p>
      ) : (
        <div className="space-y-3">
          <EvidenceScatter findings={findings} />
          <div className="space-y-1.5">
          {findings.map((f, i) => {
            const imp = IMPACT_STYLE[f.risk_impact] || IMPACT_STYLE.neutral
            const tier = f.source_tier || 'general'
            return (
              <div key={i} className={`bg-white rounded border-l-4 px-3 py-2 ${imp.border} border border-slate-200`}>
                <div className="flex flex-wrap gap-1.5 items-center mb-1">
                  <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded uppercase ${imp.badge}`}>
                    {f.risk_impact}
                  </span>
                  <span className={`text-[11px] px-1.5 py-0.5 rounded border font-medium capitalize ${SOURCE_TIER_BADGE[tier] || SOURCE_TIER_BADGE.general}`}>
                    {tier}
                  </span>
                  <span className="text-[11px] text-slate-500 uppercase">{f.category}</span>
                  {f.insufficient_corroboration && (
                    <span className="text-[11px] bg-amber-50 border border-amber-300 text-amber-700 px-1.5 py-0.5 rounded">
                      ⚠ needs corroboration
                    </span>
                  )}
                  {f.novel === true && (
                    <span className="text-[11px] bg-purple-50 border border-purple-200 text-purple-600 px-1.5 py-0.5 rounded">novel</span>
                  )}
                  <span className="ml-auto text-[11px] text-slate-400">
                    {f.corroboration_count != null ? `${f.corroboration_count} src` : ''}{' '}
                    conf: {formatRiskScore(f.confidence ?? f.relevance_score)}
                  </span>
                </div>
                <p className="text-xs text-slate-800">{f.summary}</p>
                <a href={f.source} target="_blank" rel="noreferrer" className="text-[11px] text-blue-500 hover:underline mt-0.5 block truncate">{f.source_title || f.source}</a>
              </div>
            )
          })}
          </div>
        </div>
      )}
    </div>
  )
}
