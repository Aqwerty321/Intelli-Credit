import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts'

const LABEL_COLORS = {
  clean: '#22c55e',
  ring: '#ef4444',
  star_seller: '#f59e0b',
  dense_cluster: '#8b5cf6',
  layered_chain: '#dc2626',
}

function RadarTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-800 text-white text-[11px] px-2 py-1.5 rounded shadow">
      <p className="font-semibold capitalize">{d.label.replace('_', ' ')}</p>
      <p>{(d.probability * 100).toFixed(1)}%</p>
    </div>
  )
}

export default function ClassRadar({ classProbabilities = {} }) {
  const data = Object.entries(classProbabilities).map(([label, probability]) => ({
    label: label.replace('_', ' '),
    probability,
    fullMark: 1,
  }))

  if (!data.length) return null

  const topLabel = Object.entries(classProbabilities).sort((a, b) => b[1] - a[1])[0]
  const color = topLabel ? LABEL_COLORS[topLabel[0]] || '#3b82f6' : '#3b82f6'

  return (
    <div className="bg-white border border-slate-200 rounded px-3 py-3">
      <h3 className="text-xs font-semibold text-slate-700 mb-2">GNN Classification Radar</h3>
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} />
          <PolarRadiusAxis tick={{ fontSize: 9 }} domain={[0, 1]} tickCount={5} />
          <Tooltip content={<RadarTooltip />} />
          <Radar
            dataKey="probability"
            stroke={color}
            fill={color}
            fillOpacity={0.25}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
