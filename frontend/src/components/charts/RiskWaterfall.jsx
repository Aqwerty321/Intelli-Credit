import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from 'recharts'

const COLORS = {
  base: '#3b82f6',
  positive: '#ef4444',
  net: '#1e293b',
}

function buildWaterfallData(baseRisk, firings = []) {
  const items = [{ name: 'Base Risk', value: baseRisk, total: baseRisk, fill: COLORS.base, isBase: true }]
  let running = baseRisk
  for (const rf of firings) {
    const adj = Number(rf.risk_adjustment) || 0
    if (adj === 0) continue
    items.push({
      name: rf.rule_slug?.replace(/_/g, ' ') || rf.rule_id,
      value: adj,
      start: running,
      total: running + adj,
      fill: COLORS.positive,
      severity: rf.severity,
    })
    running += adj
  }
  items.push({ name: 'Final', value: running, total: running, fill: COLORS.net, isNet: true })
  return items
}

function WaterfallBar(props) {
  const { x, y, width, height, payload } = props
  if (payload.isBase || payload.isNet) {
    return <rect x={x} y={y} width={width} height={Math.abs(height)} rx={2} fill={payload.fill} />
  }
  const barY = Math.min(y, y + height)
  return <rect x={x} y={barY} width={width} height={Math.abs(height)} rx={2} fill={payload.fill} opacity={0.85} />
}

function WaterfallTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-800 text-white text-[11px] px-2 py-1.5 rounded shadow">
      <p className="font-semibold">{d.name}</p>
      {d.isBase && <p>Base risk: {d.value.toFixed(2)}</p>}
      {d.isNet && <p>Final risk: {d.value.toFixed(2)}</p>}
      {!d.isBase && !d.isNet && (
        <>
          <p>Adjustment: +{d.value.toFixed(2)}</p>
          <p>Running: {d.total.toFixed(2)}</p>
          {d.severity && <p>Severity: {d.severity}</p>}
        </>
      )}
    </div>
  )
}

export default function RiskWaterfall({ baseRisk = 0, firings = [] }) {
  const data = buildWaterfallData(baseRisk, firings)

  if (!firings.length) return null

  return (
    <div className="bg-white border border-slate-200 rounded px-3 py-3">
      <h3 className="text-xs font-semibold text-slate-700 mb-2">Risk Score Waterfall</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" height={50} />
          <YAxis tick={{ fontSize: 10 }} domain={[0, 'auto']} />
          <Tooltip content={<WaterfallTooltip />} />
          <ReferenceLine y={1} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Max', fontSize: 10, fill: '#ef4444' }} />
          <Bar dataKey="total" shape={<WaterfallBar />} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
