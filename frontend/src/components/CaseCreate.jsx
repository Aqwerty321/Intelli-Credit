import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createCase } from '../services/api'

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
      const data = await createCase({ ...form, loan_amount: parseFloat(form.loan_amount) })
      nav(`/cases/${data.case_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const inp = (label, key, type = 'text', placeholder = '') => (
    <div>
      <label className="block text-xs font-medium text-slate-500 mb-1">{label}</label>
      <input
        type={type}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full border border-slate-200 rounded px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-brand/30 focus:border-brand focus:outline-none"
        required={key === 'company_name' || key === 'loan_amount'}
      />
    </div>
  )

  return (
    <div className="max-w-2xl">
      <h1 className="text-lg font-semibold text-slate-900 mb-4">New Credit Case</h1>
      {error && <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-white rounded border border-slate-200 p-5 space-y-4">
        {inp('Company Name *', 'company_name', 'text', 'e.g. Apex Gears Pvt Ltd')}
        {inp('Loan Amount Requested (₹) *', 'loan_amount', 'number', '5000000')}

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Loan Purpose</label>
          <select
            value={form.loan_purpose}
            onChange={e => setForm(f => ({ ...f, loan_purpose: e.target.value }))}
            className="w-full border border-slate-200 rounded px-3 py-1.5 text-sm bg-white focus:ring-2 focus:ring-brand/30 focus:border-brand focus:outline-none"
          >
            {['Working Capital', 'Term Loan', 'Equipment Finance', 'Trade Finance', 'MSME Loan'].map(p => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {inp('Sector', 'sector', 'text', 'e.g. Automotive Components')}
          {inp('Location', 'location', 'text', 'e.g. Pune, Maharashtra')}
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full py-2 bg-brand text-white rounded text-sm font-medium hover:bg-brand-dark disabled:opacity-50 transition-colors"
        >
          {saving ? 'Creating…' : 'Create Case →'}
        </button>
      </form>
    </div>
  )
}
