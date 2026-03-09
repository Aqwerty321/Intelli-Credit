import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

function riskColor(score) {
  if (score <= 0.3) return '#22c55e'
  if (score <= 0.6) return '#f59e0b'
  return '#ef4444'
}

export default function RiskGauge({ riskScore = 0, size = 90 }) {
  const score = Math.max(0, Math.min(1, riskScore))
  const color = riskColor(score)
  const data = [
    { value: score },
    { value: 1 - score },
  ]

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            startAngle={220}
            endAngle={-40}
            innerRadius="62%"
            outerRadius="92%"
            paddingAngle={0}
            dataKey="value"
            isAnimationActive={false}
            stroke="none"
          >
            <Cell fill={color} />
            <Cell fill="#e2e8f0" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <span
        className="absolute inset-0 flex items-center justify-center font-bold leading-none pointer-events-none"
        style={{ color, fontSize: Math.max(9, Math.round(size * 0.21)) }}
      >
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  )
}
