import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import ConfirmModal from './ConfirmModal'
import { deleteCase, listCases } from '../services/api'

const VERDICT_DOT = {
  APPROVE: 'bg-green-500',
  CONDITIONAL: 'bg-amber-500',
  REJECT: 'bg-red-500',
}

const VERDICT_TEXT = {
  APPROVE: 'text-green-700',
  CONDITIONAL: 'text-amber-700',
  REJECT: 'text-red-700',
}

function formatRiskScore(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '—'
}

function relativeTime(isoStr) {
  if (!isoStr) return ''
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  return new Date(isoStr).toLocaleDateString()
}

export default function CaseList() {
  const location = useLocation()
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleteCaseId, setDeleteCaseId] = useState(null)
  const [deleteError, setDeleteError] = useState('')
  const presentationMode = new URLSearchParams(location.search).get('presentation') === '1' || import.meta.env.VITE_PRESENTATION_MODE === '1'

  function reload() {
    setLoading(true)
    listCases()
      .then(data => {
        const sorted = [...data].sort((a, b) => {
          if (presentationMode) {
            const rankA = a.demo_rank ?? Number.MAX_SAFE_INTEGER
            const rankB = b.demo_rank ?? Number.MAX_SAFE_INTEGER
            if (rankA !== rankB) return rankA - rankB
          }
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        })
        setCases(sorted)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => { reload() }, [presentationMode])

  async function handleDeleteCase() {
    try {
      await deleteCase(deleteCaseId)
      setDeleteCaseId(null)
      reload()
    } catch (e) {
      setDeleteError(e.message || 'Delete failed')
      setDeleteCaseId(null)
    }
  }

  if (loading) return <p className="text-slate-400 py-10 text-center text-sm">Loading cases…</p>

  const pendingCase = cases.find(c => c.case_id === deleteCaseId)

  // Summary stats
  const completedCases = cases.filter(c => c.status === 'complete')
  const decisionCounts = cases.reduce((acc, item) => {
    if (item.recommendation) acc[item.recommendation] = (acc[item.recommendation] || 0) + 1
    return acc
  }, {})
  const avgRisk = completedCases.length
    ? completedCases.reduce((sum, item) => sum + (Number(item.risk_score) || 0), 0) / completedCases.length
    : null

  if (!cases.length) {
    return (
      <div className="text-center py-16">
        {deleteError && <p className="text-red-600 mb-4 text-sm">{deleteError}</p>}
        <p className="text-slate-400 text-sm mb-4">No cases yet.</p>
        <Link to="/cases/new" className="px-4 py-2 bg-brand text-white rounded text-sm font-medium hover:bg-brand-dark">
          Create your first case →
        </Link>
      </div>
    )
  }

  return (
    <div>
      <ConfirmModal
        open={!!deleteCaseId}
        title="Delete Case"
        body={`Permanently delete "${pendingCase?.company_name}"? This cannot be undone.`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDeleteCase}
        onCancel={() => setDeleteCaseId(null)}
      />

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Total Cases', value: cases.length },
          { label: 'Approved', value: decisionCounts.APPROVE || 0 },
          { label: 'Conditional', value: decisionCounts.CONDITIONAL || 0 },
          { label: 'Avg Risk', value: formatRiskScore(avgRisk) },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white border border-slate-200 rounded px-3 py-2">
            <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{kpi.label}</p>
            <p className="text-lg font-semibold text-slate-900 mt-0.5">{kpi.value}</p>
          </div>
        ))}
      </div>

      {deleteError && <p className="text-red-600 mb-3 text-xs">{deleteError}</p>}

      {/* Dense table */}
      <div className="bg-white border border-slate-200 rounded overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-100 border-b border-slate-200">
              {['Company', 'Loan Amount', 'Purpose', 'Status', 'Decision', 'Risk Score', 'Created', 'Actions'].map(h => (
                <th
                  key={h}
                  className={`px-3 py-2 text-left text-[11px] uppercase tracking-wider text-slate-500 font-semibold ${
                    h === 'Loan Amount' || h === 'Risk Score' ? 'text-right' : ''
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {cases.map(c => (
              <tr key={c.case_id} className="hover:bg-slate-50">
                <td className="px-3 py-2 font-medium">
                  <Link to={`/cases/${c.case_id}${presentationMode ? '?presentation=1' : ''}`} className="text-brand hover:underline">
                    {c.company_name}
                  </Link>
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-700">
                  ₹{Number(c.loan_amount).toLocaleString('en-IN')}
                </td>
                <td className="px-3 py-2 text-slate-600">{c.loan_purpose}</td>
                <td className="px-3 py-2">
                  <span className="text-slate-500 capitalize">{c.status}</span>
                </td>
                <td className="px-3 py-2">
                  <span className="inline-flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${VERDICT_DOT[c.recommendation] || 'bg-slate-300'}`} />
                    <span className={`font-semibold ${VERDICT_TEXT[c.recommendation] || 'text-slate-400'}`}>
                      {c.recommendation ?? '—'}
                    </span>
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono text-slate-700">
                  {formatRiskScore(c.risk_score)}
                </td>
                <td className="px-3 py-2 text-[11px] text-slate-400">
                  {relativeTime(c.created_at)}
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => { setDeleteError(''); setDeleteCaseId(c.case_id) }}
                    className="text-red-400 hover:text-red-600 text-[11px] font-medium"
                    title="Delete case"
                  >
                    🗑 Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
