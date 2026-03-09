import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listCases, compareCases } from '../services/api'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

const VERDICT_COLORS = { APPROVE: '#22c55e', CONDITIONAL: '#f59e0b', REJECT: '#ef4444' }
const VERDICT_TEXT = { APPROVE: 'text-green-700', CONDITIONAL: 'text-amber-700', REJECT: 'text-red-700' }
const VERDICT_BG = { APPROVE: 'bg-green-50', CONDITIONAL: 'bg-amber-50', REJECT: 'bg-red-50' }

function MiniGauge({ score, size = 52 }) {
  const s = Math.max(0, Math.min(1, score || 0))
  const color = s <= 0.3 ? '#22c55e' : s <= 0.6 ? '#f59e0b' : '#ef4444'
  const data = [{ value: s }, { value: 1 - s }]
  return (
    <div className="flex flex-col items-center" style={{ width: size, height: size + 10 }}>
      <ResponsiveContainer width={size} height={size}>
        <PieChart>
          <Pie data={data} startAngle={220} endAngle={-40} innerRadius="60%" outerRadius="95%"
               paddingAngle={0} dataKey="value" isAnimationActive={false} stroke="none">
            <Cell fill={color} /><Cell fill="#e2e8f0" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <span className="text-[10px] font-bold -mt-3" style={{ color }}>{(s * 100).toFixed(0)}%</span>
    </div>
  )
}

function MetricRow({ label, values, format, highlight }) {
  return (
    <tr className="border-b border-slate-100">
      <td className="px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase tracking-wider bg-slate-50 w-40">{label}</td>
      {values.map((v, i) => {
        const formatted = format ? format(v) : (v ?? '—')
        const cls = highlight ? highlight(v) : ''
        return (
          <td key={i} className={`px-3 py-2 text-xs text-slate-700 ${cls}`}>{formatted}</td>
        )
      })}
    </tr>
  )
}

export default function CaseCompare() {
  const [allCases, setAllCases] = useState([])
  const [selected, setSelected] = useState([])
  const [compareData, setCompareData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    listCases()
      .then(data => {
        // Only show completed cases
        setAllCases(data.filter(c => c.status === 'complete'))
      })
      .catch(() => {})
  }, [])

  function toggleCase(caseId) {
    setSelected(prev => {
      if (prev.includes(caseId)) return prev.filter(id => id !== caseId)
      if (prev.length >= 5) return prev
      return [...prev, caseId]
    })
    setCompareData(null)
  }

  async function runCompare() {
    if (selected.length < 2) return
    setLoading(true)
    setError(null)
    try {
      const data = await compareCases(selected)
      setCompareData(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-bold text-slate-800">Case Comparison</h1>
        <Link to="/" className="text-xs text-brand hover:underline">← Back to Dashboard</Link>
      </div>

      {/* Case selector */}
      <div className="bg-white border border-slate-200 rounded-lg px-4 py-3 mb-5">
        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
          Select Cases to Compare <span className="text-slate-400 normal-case font-normal">(2 – 5 cases)</span>
        </h3>
        {!allCases.length && <p className="text-xs text-slate-400">No completed cases available for comparison.</p>}
        <div className="flex flex-wrap gap-2">
          {allCases.map(c => {
            const isSelected = selected.includes(c.case_id)
            return (
              <button
                key={c.case_id}
                onClick={() => toggleCase(c.case_id)}
                className={`px-3 py-1.5 rounded text-xs font-medium border transition-colors ${
                  isSelected
                    ? 'bg-brand text-white border-brand'
                    : 'bg-slate-50 text-slate-600 border-slate-200 hover:border-brand hover:text-brand'
                }`}
              >
                {c.company_name}
                {c.risk_score != null && <span className="ml-1 opacity-75">({Number(c.risk_score).toFixed(2)})</span>}
              </button>
            )
          })}
        </div>
        <div className="flex items-center gap-3 mt-3">
          <button
            onClick={runCompare}
            disabled={selected.length < 2 || loading}
            className="px-4 py-1.5 bg-brand text-white rounded text-xs font-medium hover:bg-brand-dark disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Comparing…' : `Compare ${selected.length} Cases`}
          </button>
          {selected.length > 0 && (
            <button onClick={() => { setSelected([]); setCompareData(null) }} className="text-xs text-slate-400 hover:text-slate-600">
              Clear selection
            </button>
          )}
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
      </div>

      {/* Comparison table */}
      {compareData && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          {/* Header with gauges */}
          <div className="grid border-b border-slate-200" style={{ gridTemplateColumns: `160px repeat(${compareData.length}, 1fr)` }}>
            <div className="bg-slate-50 px-3 py-3 border-r border-slate-200" />
            {compareData.map(c => (
              <div key={c.case_id} className="px-3 py-3 border-r border-slate-100 last:border-0 text-center">
                <Link to={`/cases/${c.case_id}`} className="text-xs font-semibold text-brand hover:underline block truncate">
                  {c.company_name}
                </Link>
                <div className="flex justify-center mt-2">
                  <MiniGauge score={c.risk_score} />
                </div>
                {c.recommendation && (
                  <span className={`inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-bold ${VERDICT_BG[c.recommendation]} ${VERDICT_TEXT[c.recommendation]}`}>
                    {c.recommendation}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Metric rows */}
          <table className="w-full text-xs">
            <tbody>
              <MetricRow
                label="Loan Amount"
                values={compareData.map(c => c.loan_amount)}
                format={v => v ? `₹${Number(v).toLocaleString('en-IN')}` : '—'}
              />
              <MetricRow
                label="Sector"
                values={compareData.map(c => c.sector || '—')}
              />
              <MetricRow
                label="Risk Score"
                values={compareData.map(c => c.risk_score)}
                format={v => v != null ? Number(v).toFixed(2) : '—'}
                highlight={v => {
                  const n = Number(v)
                  if (!Number.isFinite(n)) return ''
                  return n <= 0.3 ? 'text-green-600 font-semibold' : n <= 0.6 ? 'text-amber-600 font-semibold' : 'text-red-600 font-semibold'
                }}
              />
              <MetricRow
                label="Sanction Amount"
                values={compareData.map(c => c.recommended_amount)}
                format={v => v ? `₹${Number(v).toLocaleString('en-IN')}` : '—'}
              />
              <MetricRow
                label="Rules Fired"
                values={compareData.map(c => c.rules_fired_count)}
                format={v => v ?? 0}
                highlight={v => v > 0 ? 'text-amber-600 font-semibold' : ''}
              />
              <MetricRow
                label="Graph Nodes"
                values={compareData.map(c => c.graph_trace?.node_count)}
                format={v => v ?? 0}
              />
              <MetricRow
                label="Graph Edges"
                values={compareData.map(c => c.graph_trace?.edge_count)}
                format={v => v ?? 0}
              />
              <MetricRow
                label="Suspicious Cycles"
                values={compareData.map(c => c.graph_trace?.suspicious_cycles)}
                format={v => v ?? 0}
                highlight={v => v > 0 ? 'text-red-600 font-semibold' : 'text-green-600'}
              />
              <MetricRow
                label="GNN Classification"
                values={compareData.map(c => c.graph_trace?.gnn_label)}
                format={v => v ? v.replace(/_/g, ' ') : '—'}
                highlight={v => v && v !== 'clean' ? 'text-red-600 font-semibold' : 'text-green-600'}
              />
              <MetricRow
                label="GNN Risk"
                values={compareData.map(c => c.graph_trace?.gnn_risk_score)}
                format={v => v != null ? Number(v).toFixed(2) : '—'}
              />
              <MetricRow
                label="Fraud Alerts"
                values={compareData.map(c => c.graph_trace?.fraud_alerts?.length)}
                format={v => v ?? 0}
                highlight={v => v > 0 ? 'text-red-600 font-semibold' : ''}
              />
            </tbody>
          </table>

          {/* Rule firing breakdown per case */}
          {compareData.some(c => c.rule_firings?.length > 0) && (
            <div className="border-t border-slate-200 px-4 py-3">
              <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">Rule Firings Detail</h3>
              <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${compareData.length}, 1fr)` }}>
                {compareData.map(c => (
                  <div key={c.case_id}>
                    <p className="text-[11px] font-semibold text-slate-600 mb-1.5 truncate">{c.company_name}</p>
                    {c.rule_firings?.length ? (
                      <div className="space-y-1">
                        {c.rule_firings.map((rf, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-[10px]">
                            <span className={`px-1.5 py-0.5 rounded font-medium ${
                              rf.severity === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                              rf.severity === 'HIGH' ? 'bg-amber-100 text-amber-700' :
                              'bg-slate-100 text-slate-600'
                            }`}>
                              +{(rf.risk_adjustment || 0).toFixed(2)}
                            </span>
                            <span className="text-slate-500 truncate">{(rf.rule_slug || rf.rule_id || '').replace(/_/g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[10px] text-green-600">No rules triggered ✓</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
