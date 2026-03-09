import { formatRiskScore, formatCurrency, asNumber, VERDICT_STYLE } from '../../utils/formatters'
import { downloadCAMUrl, downloadCAMPdfUrl } from '../../services/api'

export default function CAMPanel({ caseId, decision, trace, hasRun }) {
  if (!hasRun) {
    return (
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-2">Credit Appraisal Memo</h2>
        <p className="text-slate-400 text-xs">Run the appraisal to generate the CAM.</p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-700 mb-3">Credit Appraisal Memo</h2>
      <div className="grid grid-cols-3 gap-3 mb-3">
        {[
          ['Recommendation', decision.recommendation],
          ['Risk Score', formatRiskScore(decision.risk_score)],
          ['Sanction', asNumber(decision.recommended_amount) > 0 ? formatCurrency(decision.recommended_amount) : '—'],
        ].map(([k, v]) => (
          <div key={k} className="bg-white rounded border border-slate-200 px-3 py-2">
            <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{k}</p>
            <p className={`text-base font-semibold mt-0.5 ${k === 'Recommendation' ? (VERDICT_STYLE[v]?.split(' ')[2] || '') : 'text-slate-900'}`}>{v ?? '—'}</p>
          </div>
        ))}
      </div>
      <div className="flex gap-2 items-center">
        <a
          href={downloadCAMPdfUrl(caseId)}
          download
          className="inline-block px-3 py-1.5 bg-brand text-white rounded text-xs font-medium hover:bg-brand-dark"
        >
          ⬇ Download PDF
        </a>
        <a
          href={downloadCAMUrl(caseId)}
          download
          className="inline-block px-3 py-1.5 bg-slate-100 text-slate-700 rounded text-xs font-medium hover:bg-slate-200"
        >
          ⬇ Markdown
        </a>
        <span className="text-[11px] text-slate-400">
          {trace.rules_fired_count != null ? `${trace.rules_fired_count} rules` : ''}
          {trace.schema_version && ` · schema ${trace.schema_version}`}
        </span>
      </div>
    </div>
  )
}
