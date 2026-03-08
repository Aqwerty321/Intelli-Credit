import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ConfirmModal from './ConfirmModal'
import { deleteCase } from '../services/api'

const BADGE = {
  APPROVE: 'bg-green-100 text-green-800',
  CONDITIONAL: 'bg-yellow-100 text-yellow-800',
  REJECT: 'bg-red-100 text-red-800',
  null: 'bg-gray-100 text-gray-600',
}

export default function CaseList() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleteCaseId, setDeleteCaseId] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  function reload() {
    setLoading(true)
    fetch('/api/cases/')
      .then(r => r.json())
      .then(data => { setCases(data); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { reload() }, [])

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

  if (loading) return <p className="text-gray-500 py-10 text-center">Loading cases…</p>

  if (!cases.length) {
    return (
      <div className="text-center py-20">
        {deleteError && <p className="text-red-600 mb-4 text-sm">{deleteError}</p>}
        <p className="text-gray-400 text-lg mb-4">No cases yet.</p>
        <Link to="/cases/new" className="px-4 py-2 bg-brand text-white rounded hover:bg-brand-dark">
          Create your first case →
        </Link>
      </div>
    )
  }

  const pendingCase = cases.find(c => c.case_id === deleteCaseId)

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
      <h1 className="text-2xl font-semibold mb-6">Cases</h1>
      {deleteError && <p className="text-red-600 mb-3 text-sm">{deleteError}</p>}
      <div className="overflow-x-auto rounded-lg shadow">
        <table className="w-full bg-white text-sm">
          <thead className="bg-gray-100 text-gray-600 uppercase text-xs">
            <tr>
              {['Company', 'Loan Amount', 'Purpose', 'Status', 'Decision', 'Risk Score', 'Created', 'Actions'].map(h => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cases.map(c => (
              <tr key={c.case_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">
                  <Link to={`/cases/${c.case_id}`} className="text-brand hover:underline">
                    {c.company_name}
                  </Link>
                </td>
                <td className="px-4 py-3">₹{Number(c.loan_amount).toLocaleString('en-IN')}</td>
                <td className="px-4 py-3 text-gray-600">{c.loan_purpose}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 capitalize">
                    {c.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${BADGE[c.recommendation] || BADGE[null]}`}>
                    {c.recommendation ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono">
                  {c.risk_score != null ? c.risk_score.toFixed(2) : '—'}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => { setDeleteError(''); setDeleteCaseId(c.case_id) }}
                    className="text-red-500 hover:text-red-700 text-xs font-medium"
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
