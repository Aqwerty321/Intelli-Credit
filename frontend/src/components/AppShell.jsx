import { useEffect, useState } from 'react'
import { Link, useLocation, useParams, Outlet } from 'react-router-dom'
import { getHealth, listCases } from '../services/api'

const VERDICT_DOT = {
  APPROVE: 'bg-green-500',
  CONDITIONAL: 'bg-amber-500',
  REJECT: 'bg-red-500',
}

export function HealthBadge({ status }) {
  if (status === 'healthy') {
    return <span className="text-xs text-green-400 font-medium">🟢 Healthy</span>
  }
  if (status === 'offline') {
    return <span className="text-xs text-red-400 font-medium">🔴 Offline</span>
  }
  return <span className="text-xs text-slate-500">⬤ …</span>
}

function formatRiskShort(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(2) : '—'
}

export default function AppShell() {
  const location = useLocation()
  const [health, setHealth] = useState('checking')
  const [sidebarCases, setSidebarCases] = useState([])
  const presentationMode =
    new URLSearchParams(location.search).get('presentation') === '1' ||
    import.meta.env.VITE_PRESENTATION_MODE === '1'

  // Extract current caseId from path
  const pathMatch = location.pathname.match(/\/cases\/([^/]+)/)
  const activeCaseId = pathMatch ? pathMatch[1] : null

  useEffect(() => {
    async function check() {
      try {
        await getHealth()
        setHealth('healthy')
      } catch {
        setHealth('offline')
      }
    }
    check()
    const id = setInterval(check, 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    listCases()
      .then(data => {
        const sorted = [...data].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
        setSidebarCases(sorted)
      })
      .catch(() => {})
  }, [location.pathname])

  const isNewCase = location.pathname === '/cases/new'
  const isDashboard = location.pathname === '/'
  const isCaseList = location.pathname === '/cases'
  const isCompare = location.pathname === '/cases/compare'

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      {!presentationMode && (
        <aside className="w-64 shrink-0 bg-sidebar flex flex-col h-screen border-r border-sidebar-border">
          {/* Brand */}
          <div className="px-4 py-4 border-b border-sidebar-border">
            <Link to="/" className="block">
              <span className="text-base font-bold text-white tracking-tight">
                🏦 Intelli-Credit
              </span>
            </Link>
          </div>

          {/* Nav links */}
          <nav className="px-2 py-3 space-y-0.5">
            <Link
              to="/"
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors ${
                isDashboard
                  ? 'bg-sidebar-active text-white'
                  : 'text-slate-400 hover:text-white hover:bg-sidebar-hover'
              }`}
            >
              <span className="text-base">◫</span>
              Dashboard
            </Link>
            <Link
              to="/cases"
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors ${
                isCaseList
                  ? 'bg-sidebar-active text-white'
                  : 'text-slate-400 hover:text-white hover:bg-sidebar-hover'
              }`}
            >
              <span className="text-base">☰</span>
              All Cases
            </Link>
            <Link
              to="/cases/compare"
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors ${
                isCompare
                  ? 'bg-sidebar-active text-white'
                  : 'text-slate-400 hover:text-white hover:bg-sidebar-hover'
              }`}
            >
              <span className="text-base">⇋</span>
              Compare
            </Link>
            <Link
              to="/cases/new"
              className={`flex items-center gap-2 px-3 py-2 rounded text-sm font-medium transition-colors ${
                isNewCase
                  ? 'bg-sidebar-active text-white'
                  : 'text-slate-400 hover:text-white hover:bg-sidebar-hover'
              }`}
            >
              <span className="text-base">+</span>
              New Case
            </Link>
          </nav>

          {/* Divider + case list label */}
          <div className="px-4 pt-2 pb-1 border-t border-sidebar-border">
            <span className="text-[11px] uppercase tracking-wider text-sidebar-muted font-semibold">
              Cases ({sidebarCases.length})
            </span>
          </div>

          {/* Scrollable case list */}
          <div className="flex-1 overflow-y-auto px-2 pb-2 min-h-0">
            {sidebarCases.map(c => {
              const isActive = activeCaseId === c.case_id
              return (
                <Link
                  key={c.case_id}
                  to={`/cases/${c.case_id}`}
                  className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors group ${
                    isActive
                      ? 'bg-sidebar-active text-white border-l-2 border-brand-light'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-sidebar-hover'
                  }`}
                  title={c.company_name}
                >
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      VERDICT_DOT[c.recommendation] || 'bg-slate-600'
                    }`}
                  />
                  <span className="truncate flex-1 text-[13px]">{c.company_name}</span>
                  <span className="text-[11px] text-sidebar-muted font-mono shrink-0">
                    {c.risk_score != null ? formatRiskShort(c.risk_score) : ''}
                  </span>
                </Link>
              )
            })}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-sidebar-border space-y-1">
            <HealthBadge status={health} />
            <p className="text-[11px] text-sidebar-muted">v3.0 · Judge-Trustworthy</p>
          </div>
        </aside>
      )}

      {/* Main content */}
      <main
        className={`flex-1 overflow-y-auto ${
          presentationMode ? 'w-full' : ''
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 py-5">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
