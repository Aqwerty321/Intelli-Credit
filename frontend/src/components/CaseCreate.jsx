import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function CaseCreate() {
  const nav = useNavigate()
  const [form, setForm] = useState({
    company_name: '',
    loan_amount: '',
    loan_purpose: 'Working Capital',
    sector: '',
    location: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const res = await fetch('/api/cases/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, loan_amount: parseFloat(form.loan_amount) }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      nav(`/cases/${data.case_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const field = (label, key, type = 'text', placeholder = '') => (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type={type}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-brand focus:outline-none"
        required={key === 'company_name' || key === 'loan_amount'}
      />
    </div>
  )

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-semibold mb-6">New Credit Case</h1>
      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded text-sm">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
        {field('Company Name *', 'company_name', 'text', 'e.g. Apex Gears Pvt Ltd')}
        {field('Loan Amount Requested (₹) *', 'loan_amount', 'number', '5000000')}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Loan Purpose</label>
          <select
            value={form.loan_purpose}
            onChange={e => setForm(f => ({ ...f, loan_purpose: e.target.value }))}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:ring-2 focus:ring-brand focus:outline-none"
          >
            {['Working Capital', 'Term Loan', 'Equipment Finance', 'Trade Finance', 'MSME Loan'].map(p => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>

        {field('Sector', 'sector', 'text', 'e.g. Automotive Components')}
        {field('Location', 'location', 'text', 'e.g. Pune, Maharashtra')}

        <button
          type="submit"
          disabled={saving}
          className="w-full py-2 bg-brand text-white rounded font-medium hover:bg-brand-dark disabled:opacity-50 transition-colors"
        >
          {saving ? 'Creating…' : 'Create Case →'}
        </button>
      </form>
    </div>
  )
}
