import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const BADGE = {
  APPROVE: 'bg-green-100 text-green-800',
  CONDITIONAL: 'bg-yellow-100 text-yellow-800',
  REJECT: 'bg-red-100 text-red-800',
  null: 'bg-gray-100 text-gray-600',
}

export default function CaseList() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/cases/')
      .then(r => r.json())
      .then(data => { setCases(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-500 py-10 text-center">Loading cases…</p>

  if (!cases.length) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-400 text-lg mb-4">No cases yet.</p>
        <Link to="/cases/new" className="px-4 py-2 bg-brand text-white rounded hover:bg-brand-dark">
          Create your first case →
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Cases</h1>
      <div className="overflow-x-auto rounded-lg shadow">
        <table className="w-full bg-white text-sm">
          <thead className="bg-gray-100 text-gray-600 uppercase text-xs">
            <tr>
              {['Company', 'Loan Amount', 'Purpose', 'Status', 'Decision', 'Risk Score', 'Created'].map(h => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cases.map(c => (
              <tr key={c.case_id} className="hover:bg-gray-50 cursor-pointer">
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
