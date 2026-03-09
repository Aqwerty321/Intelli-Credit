import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { getDashboardStats, listCases } from '../services/api'

const VERDICT_COLORS = { APPROVE: '#22c55e', CONDITIONAL: '#f59e0b', REJECT: '#ef4444' }
const RISK_BAR_COLORS = ['#22c55e', '#86efac', '#fbbf24', '#f97316', '#ef4444']

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg px-4 py-3 flex flex-col">
      <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{label}</span>
      <span className={`text-2xl font-bold mt-1 ${accent || 'text-slate-900'}`}>{value}</span>
      {sub && <span className="text-[11px] text-slate-400 mt-0.5">{sub}</span>}
    </div>
  )
}

function VerdictPie({ data }) {
  const entries = Object.entries(data).filter(([, v]) => v > 0)
  if (!entries.length) return <p className="text-xs text-slate-400 py-8 text-center">No decisions yet</p>

  const pieData = entries.map(([name, value]) => ({ name, value }))
  const total = entries.reduce((s, [, v]) => s + v, 0)

  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width={140} height={140}>
        <PieChart>
          <Pie data={pieData} dataKey="value" cx="50%" cy="50%" innerRadius={36} outerRadius={60}
               paddingAngle={2} isAnimationActive={false} stroke="none">
            {pieData.map(d => <Cell key={d.name} fill={VERDICT_COLORS[d.name] || '#94a3b8'} />)}
          </Pie>
          <Tooltip formatter={(v, name) => [`${v} (${((v / total) * 100).toFixed(0)}%)`, name]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-1.5">
        {pieData.map(d => (
          <div key={d.name} className="flex items-center gap-2 text-xs">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: VERDICT_COLORS[d.name] }} />
            <span className="text-slate-600 font-medium">{d.name}</span>
            <span className="text-slate-400 ml-auto font-mono">{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function RiskHistogram({ distribution }) {
  if (!distribution?.length) return null
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={distribution} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="range" tick={{ fontSize: 10 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
        <Tooltip formatter={v => [v, 'Cases']} />
        <Bar dataKey="count" isAnimationActive={false} radius={[3, 3, 0, 0]}>
          {distribution.map((_, i) => <Cell key={i} fill={RISK_BAR_COLORS[i]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function RuleHeatmap({ rules }) {
  if (!rules?.length) return <p className="text-xs text-slate-400 py-4">No rules fired yet</p>
  const max = Math.max(...rules.map(r => r.count))
  return (
    <div className="space-y-1.5">
      {rules.map(r => (
        <div key={r.rule} className="flex items-center gap-2">
          <span className="text-[11px] text-slate-600 w-40 truncate" title={r.rule}>
            {r.rule.replace(/_/g, ' ')}
          </span>
          <div className="flex-1 bg-slate-100 rounded-full h-4 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(r.count / max) * 100}%`,
                background: r.count >= max * 0.8 ? '#ef4444' : r.count >= max * 0.4 ? '#f59e0b' : '#3b82f6',
              }}
            />
          </div>
          <span className="text-[11px] text-slate-500 font-mono w-6 text-right">{r.count}</span>
        </div>
      ))}
    </div>
  )
}

function ActivityTimeline({ activity }) {
  if (!activity?.length) return <p className="text-xs text-slate-400 py-4">No activity yet</p>

  function relativeTime(ts) {
    if (!ts) return ''
    const diff = Date.now() - new Date(ts).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return days < 30 ? `${days}d ago` : new Date(ts).toLocaleDateString()
  }

  const ACTION_LABEL = {
    created: 'Case created',
    documents_uploaded: 'Documents uploaded',
    complete: 'Analysis complete',
  }

  const VERDICT_DOT = { APPROVE: 'bg-green-500', CONDITIONAL: 'bg-amber-500', REJECT: 'bg-red-500' }

  return (
    <div className="space-y-0">
      {activity.slice(0, 10).map((a, i) => (
        <div key={`${a.case_id}-${i}`} className="flex items-start gap-3 py-2 border-b border-slate-100 last:border-0">
          <div className="flex flex-col items-center mt-1">
            <span className={`w-2 h-2 rounded-full ${VERDICT_DOT[a.recommendation] || 'bg-slate-300'}`} />
            {i < 9 && <div className="w-px h-full bg-slate-200 mt-1" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Link to={`/cases/${a.case_id}`} className="text-xs font-medium text-brand hover:underline truncate">
                {a.company_name}
              </Link>
              <span className="text-[10px] text-slate-400 shrink-0">{relativeTime(a.timestamp)}</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {ACTION_LABEL[a.action] || a.action}
              {a.risk_score != null && <span className="ml-2 font-mono">risk: {Number(a.risk_score).toFixed(2)}</span>}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

function SectorBreakdown({ sectors }) {
  if (!sectors?.length) return null
  const total = sectors.reduce((s, x) => s + x.count, 0)
  const SECTOR_COLORS = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#ec4899']
  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width={120} height={120}>
        <PieChart>
          <Pie data={sectors} dataKey="count" nameKey="sector" cx="50%" cy="50%" outerRadius={50}
               isAnimationActive={false} stroke="none">
            {sectors.map((_, i) => <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v, name) => [`${v} (${((v / total) * 100).toFixed(0)}%)`, name]} />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-1">
        {sectors.slice(0, 6).map((s, i) => (
          <div key={s.sector} className="flex items-center gap-2 text-[11px]">
            <span className="w-2 h-2 rounded-full" style={{ background: SECTOR_COLORS[i % SECTOR_COLORS.length] }} />
            <span className="text-slate-600 truncate max-w-[120px]">{s.sector}</span>
            <span className="text-slate-400 ml-auto font-mono">{s.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-slate-400 py-10 text-center text-sm">Loading dashboard…</p>
  if (error) return <p className="text-red-500 py-10 text-center text-sm">Error: {error}</p>
  if (!stats || stats.total_cases === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-slate-400 text-sm mb-4">No cases yet.</p>
        <Link to="/cases/new" className="px-4 py-2 bg-brand text-white rounded text-sm font-medium hover:bg-brand-dark">
          Create your first case →
        </Link>
      </div>
    )
  }

  const { decision_counts, risk_distribution, top_rules_fired, recent_activity, sector_breakdown } = stats

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-bold text-slate-800">Portfolio Dashboard</h1>
        <Link to="/cases/compare" className="px-3 py-1.5 bg-slate-100 text-slate-700 hover:bg-slate-200 rounded text-xs font-medium transition-colors">
          Compare Cases →
        </Link>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
        <StatCard label="Total Cases" value={stats.total_cases} sub={`${stats.completed_cases} completed`} />
        <StatCard label="Approved" value={decision_counts.APPROVE || 0} accent="text-green-600" />
        <StatCard label="Conditional" value={decision_counts.CONDITIONAL || 0} accent="text-amber-600" />
        <StatCard label="Rejected" value={decision_counts.REJECT || 0} accent="text-red-600" />
        <StatCard label="Avg Risk" value={stats.avg_risk != null ? stats.avg_risk.toFixed(2) : '—'} accent="text-slate-800" />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
          <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">Verdict Distribution</h3>
          <VerdictPie data={decision_counts} />
        </div>
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
          <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">Risk Score Distribution</h3>
          <RiskHistogram distribution={risk_distribution} />
        </div>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
          <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">Top Rules Fired</h3>
          <RuleHeatmap rules={top_rules_fired} />
        </div>
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
          <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">Sector Breakdown</h3>
          <SectorBreakdown sectors={sector_breakdown} />
        </div>
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-3">
          <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">Recent Activity</h3>
          <ActivityTimeline activity={recent_activity} />
        </div>
      </div>
    </div>
  )
}
