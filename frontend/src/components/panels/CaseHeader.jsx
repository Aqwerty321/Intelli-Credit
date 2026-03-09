import { formatCurrency, VERDICT_STYLE, RISK_COLOR, formatRiskScore } from '../../utils/formatters'
import ConfirmModal from '../ConfirmModal'

export default function CaseHeader({ caseData, hasRun, decision, firings, findings, showDeleteCase, setShowDeleteCase, onDeleteCase, presentationMode }) {
  return (
    <>
      <ConfirmModal
        open={showDeleteCase}
        title="Delete Case"
        body={`This will permanently delete all files for "${caseData.company_name}". This cannot be undone.`}
        confirmLabel="Delete Case"
        onConfirm={onDeleteCase}
        onCancel={() => setShowDeleteCase(false)}
      />

      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 leading-tight">{caseData.company_name}</h1>
          <p className="text-slate-500 text-xs mt-1">
            {formatCurrency(caseData.loan_amount)} · {caseData.loan_purpose}
            {caseData.sector && ` · ${caseData.sector}`}
            {caseData.location && `, ${caseData.location}`}
          </p>
        </div>
        {!presentationMode && (
          <button
            onClick={() => setShowDeleteCase(true)}
            className="shrink-0 text-xs text-red-400 hover:text-red-600 font-medium"
          >
            🗑 Delete
          </button>
        )}
      </div>

      {/* Verdict banner */}
      {hasRun && (
        <div className={`rounded border-l-4 px-4 py-3 mb-4 ${VERDICT_STYLE[decision.recommendation] || ''}`}>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-lg font-bold">{decision.recommendation}</span>
            <span className={`text-base font-mono font-semibold ${RISK_COLOR(decision.risk_score)}`}>
              Risk: {formatRiskScore(decision.risk_score)}
            </span>
            {Number(decision.recommended_amount) > 0 && (
              <span className="text-xs text-slate-600">Sanction: {formatCurrency(decision.recommended_amount)}</span>
            )}
            <span className="text-[11px] text-slate-500 ml-auto">
              {firings.length} rule{firings.length !== 1 ? 's' : ''} fired · {findings.length} evidence item{findings.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      )}
    </>
  )
}
