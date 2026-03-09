import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const IMPACT_COLORS = {
  negative: '#ef4444',
  positive: '#22c55e',
  neutral: '#3b82f6',
  stale_negative: '#fca5a5',
  stale_positive: '#86efac',
}

function ScatterTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-800 text-white text-[11px] px-2 py-1.5 rounded shadow max-w-xs">
      <p className="font-semibold mb-0.5">{d.category}</p>
      <p className="text-slate-300">{d.summary?.slice(0, 120)}</p>
      <div className="flex gap-2 mt-1">
        <span>Conf: {(d.confidence * 100).toFixed(0)}%</span>
        <span>Tier: {d.source_tier}</span>
        <span className="capitalize">{d.risk_impact}</span>
      </div>
    </div>
  )
}

export default function EvidenceScatter({ findings = [] }) {
  if (!findings.length) return null

  const data = findings.map((f, i) => ({
    x: f.confidence ?? f.relevance_score ?? 0.5,
    y: f.corroboration_count ?? 0,
    category: f.category,
    summary: f.summary,
    risk_impact: f.risk_impact,
    confidence: f.confidence ?? f.relevance_score ?? 0.5,
    source_tier: f.source_tier || 'general',
    size: f.corroboration_count ? Math.min(60, 20 + f.corroboration_count * 15) : 20,
  }))

  return (
    <div className="bg-white border border-slate-200 rounded px-3 py-3">
      <h3 className="text-xs font-semibold text-slate-700 mb-2">Evidence Confidence × Corroboration</h3>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" dataKey="x" name="Confidence" domain={[0, 1]} tick={{ fontSize: 10 }} label={{ value: 'Confidence', position: 'bottom', fontSize: 10, offset: -2 }} />
          <YAxis type="number" dataKey="y" name="Sources" tick={{ fontSize: 10 }} label={{ value: 'Sources', angle: -90, position: 'insideLeft', fontSize: 10 }} />
          <Tooltip content={<ScatterTooltip />} />
          <Scatter data={data} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={IMPACT_COLORS[d.risk_impact] || IMPACT_COLORS.neutral} r={d.size / 5} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      {/* Mini legend */}
      <div className="flex gap-3 mt-1 text-[10px] text-slate-500">
        {Object.entries(IMPACT_COLORS).filter(([k]) => !k.startsWith('stale')).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: color }} />
            <span className="capitalize">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
