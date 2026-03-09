import { useState, useCallback } from 'react'
import { inferFromTransactions, whatIf } from '../../services/gnn'

const ROLE_OPTIONS = ['borrower', 'supplier', 'buyer', 'related_party', 'shell', 'distributor', 'bank', 'customer']

function ProbBar({ label, value, isTop }) {
  const pct = (value * 100).toFixed(1)
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="w-24 text-right text-slate-500 capitalize">{label.replace('_', ' ')}</span>
      <div className="flex-1 h-3 bg-slate-100 rounded overflow-hidden">
        <div
          className={`h-full rounded ${isTop ? 'bg-brand' : 'bg-slate-300'}`}
          style={{ width: `${Math.max(value * 100, 1)}%` }}
        />
      </div>
      <span className={`w-12 text-right font-mono ${isTop ? 'font-bold text-brand' : 'text-slate-400'}`}>{pct}%</span>
    </div>
  )
}

export default function GraphPlayground({ transactions = [] }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [whatIfResult, setWhatIfResult] = useState(null)

  // What-if form state
  const [removeIdx, setRemoveIdx] = useState('')
  const [addSource, setAddSource] = useState('')
  const [addTarget, setAddTarget] = useState('')
  const [addAmount, setAddAmount] = useState('')
  const [addSourceRole, setAddSourceRole] = useState('supplier')
  const [addTargetRole, setAddTargetRole] = useState('buyer')

  const runInference = useCallback(async () => {
    if (!transactions.length) return
    setLoading(true)
    setError('')
    try {
      const res = await inferFromTransactions(transactions)
      setResult(res)
    } catch (e) {
      setError(e.message || 'Inference failed')
    } finally {
      setLoading(false)
    }
  }, [transactions])

  const runWhatIf = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const mod = {}
      if (removeIdx !== '') mod.removeIndex = parseInt(removeIdx, 10)
      if (addSource && addTarget && addAmount) {
        mod.addTransaction = {
          source: addSource,
          target: addTarget,
          amount: parseFloat(addAmount),
          source_role: addSourceRole,
          target_role: addTargetRole,
          type: 'GST_INVOICE',
        }
      }
      const res = await whatIf(transactions, mod)
      setWhatIfResult(res)
    } catch (e) {
      setError(e.message || 'What-if failed')
    } finally {
      setLoading(false)
    }
  }, [transactions, removeIdx, addSource, addTarget, addAmount, addSourceRole, addTargetRole])

  if (!transactions.length) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded px-3 py-4 text-sm text-slate-400 text-center">
        No transaction data available for GNN playground
      </div>
    )
  }

  const topLabel = result ? Object.entries(result.probabilities).sort((a, b) => b[1] - a[1])[0][0] : null

  return (
    <div className="bg-white border border-slate-200 rounded px-3 py-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-700">GNN Playground (Browser ONNX)</h3>
        <button
          onClick={runInference}
          disabled={loading}
          className="text-[11px] bg-brand text-white px-3 py-1 rounded hover:bg-brand/90 disabled:opacity-50"
        >
          {loading ? 'Running…' : 'Run Inference'}
        </button>
      </div>

      {error && <p className="text-[11px] text-red-600 bg-red-50 px-2 py-1 rounded">{error}</p>}

      {/* Baseline result */}
      {result && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${
              topLabel === 'clean' ? 'bg-green-100 text-green-700' :
              topLabel === 'ring' ? 'bg-red-100 text-red-700' :
              'bg-amber-100 text-amber-700'
            }`}>{topLabel?.replace('_', ' ')}</span>
            <span className="text-[11px] text-slate-400">{result.numNodes} nodes</span>
          </div>
          {Object.entries(result.probabilities).map(([label, prob]) => (
            <ProbBar key={label} label={label} value={prob} isTop={label === topLabel} />
          ))}
        </div>
      )}

      {/* What-if controls */}
      {result && (
        <details className="border-t border-slate-200 pt-2">
          <summary className="text-xs font-semibold text-slate-700 cursor-pointer select-none">
            What-If Sandbox
          </summary>
          <div className="mt-2 space-y-2">
            {/* Remove edge */}
            <div className="flex items-center gap-2">
              <label className="text-[11px] text-slate-500 w-24">Remove edge #</label>
              <input
                type="number"
                min="0"
                max={transactions.length - 1}
                value={removeIdx}
                onChange={e => setRemoveIdx(e.target.value)}
                className="flex-1 text-xs border border-slate-200 rounded px-2 py-1"
                placeholder="index"
              />
            </div>
            {/* Add edge */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] text-slate-500">Source</label>
                <input value={addSource} onChange={e => setAddSource(e.target.value)}
                  className="w-full text-xs border border-slate-200 rounded px-2 py-1" placeholder="Entity name" />
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Target</label>
                <input value={addTarget} onChange={e => setAddTarget(e.target.value)}
                  className="w-full text-xs border border-slate-200 rounded px-2 py-1" placeholder="Entity name" />
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Amount</label>
                <input type="number" value={addAmount} onChange={e => setAddAmount(e.target.value)}
                  className="w-full text-xs border border-slate-200 rounded px-2 py-1" placeholder="₹" />
              </div>
              <div className="flex gap-1">
                <div className="flex-1">
                  <label className="text-[11px] text-slate-500">Src Role</label>
                  <select value={addSourceRole} onChange={e => setAddSourceRole(e.target.value)}
                    className="w-full text-xs border border-slate-200 rounded px-1 py-1">
                    {ROLE_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-[11px] text-slate-500">Tgt Role</label>
                  <select value={addTargetRole} onChange={e => setAddTargetRole(e.target.value)}
                    className="w-full text-xs border border-slate-200 rounded px-1 py-1">
                    {ROLE_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              </div>
            </div>
            <button
              onClick={runWhatIf}
              disabled={loading}
              className="text-[11px] bg-amber-500 text-white px-3 py-1 rounded hover:bg-amber-600 disabled:opacity-50"
            >
              {loading ? 'Computing…' : 'Run What-If'}
            </button>

            {whatIfResult && (
              <div className="bg-amber-50 border border-amber-200 rounded px-2 py-2 mt-1 space-y-1">
                <p className="text-[11px] font-semibold text-amber-800">What-If Result</p>
                {Object.entries(whatIfResult.probabilities).map(([label, prob]) => {
                  const baseline = result.probabilities[label] || 0
                  const delta = prob - baseline
                  return (
                    <div key={label} className="flex items-center gap-2 text-[11px]">
                      <span className="w-24 text-right text-slate-500 capitalize">{label.replace('_', ' ')}</span>
                      <span className="w-14 text-right font-mono">{(prob * 100).toFixed(1)}%</span>
                      <span className={`w-14 text-right font-mono ${delta > 0.01 ? 'text-red-600' : delta < -0.01 ? 'text-green-600' : 'text-slate-400'}`}>
                        {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  )
}
