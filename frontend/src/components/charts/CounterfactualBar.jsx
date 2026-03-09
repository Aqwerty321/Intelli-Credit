import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from 'recharts'

const REC_COLORS = {
  APPROVE: '#22c55e',
  CONDITIONAL: '#f59e0b',
  REJECT: '#ef4444',
}

function CfTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-800 text-white text-[11px] px-2 py-1.5 rounded shadow max-w-xs">
      <p className="font-semibold">{d.description}</p>
      <p className="mt-0.5">Δ risk: {d.delta > 0 ? '+' : ''}{(d.delta * 100).toFixed(0)}%</p>
      <p>→ {d.recommendation}</p>
      {d.rationale && <p className="text-slate-300 mt-0.5">{d.rationale.slice(0, 100)}</p>}
    </div>
  )
}

export default function CounterfactualBar({ scenarios = [] }) {
  if (!scenarios.length) return null

  const data = scenarios.map(s => ({
    name: s.description?.length > 25 ? s.description.slice(0, 23) + '…' : s.description,
    description: s.description,
    delta: s.delta_risk_score ?? 0,
    recommendation: s.hypothetical_recommendation || '—',
    rationale: s.rationale,
    fill: REC_COLORS[s.hypothetical_recommendation] || '#94a3b8',
  }))

  return (
    <div className="bg-white border border-slate-200 rounded px-3 py-3">
      <h3 className="text-xs font-semibold text-slate-700 mb-2">What-If Scenarios (Risk Delta)</h3>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 40 + 40)}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 15, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => `${v > 0 ? '+' : ''}${(v * 100).toFixed(0)}%`} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={140} />
          <Tooltip content={<CfTooltip />} />
          <ReferenceLine x={0} stroke="#94a3b8" />
          <Bar dataKey="delta" isAnimationActive={false} barSize={18}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} radius={[0, 3, 3, 0]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
