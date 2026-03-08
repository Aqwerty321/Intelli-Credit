import { Routes, Route, Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import CaseList from './components/CaseList'
import CaseCreate from './components/CaseCreate'
import CaseDetail from './components/CaseDetail'
import { getHealth } from './services/api'

function HealthBadge({ status }) {
  if (status === 'healthy') {
    return <span className="text-xs text-green-300 font-medium">🟢 Healthy</span>
  }
  if (status === 'offline') {
    return <span className="text-xs text-red-300 font-medium animate-pulse">🔴 Offline</span>
  }
  return <span className="text-xs text-gray-400">⬤ …</span>
}

export default function App() {
  const [health, setHealth] = useState('checking')

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

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <header className="bg-brand text-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
          <Link to="/" className="text-xl font-bold tracking-tight">
            🏦 Intelli-Credit
          </Link>
          <Link to="/cases/new" className="text-sm bg-white text-brand px-3 py-1 rounded font-medium hover:bg-blue-50 transition-colors">
            + New Case
          </Link>
          <div className="ml-auto flex items-center gap-4">
            <HealthBadge status={health} />
            <span className="text-xs opacity-70">v3.0 · Judge-Trustworthy</span>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <Routes>
          <Route path="/" element={<CaseList />} />
          <Route path="/cases/new" element={<CaseCreate />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
        </Routes>
      </main>
    </div>
  )
}
