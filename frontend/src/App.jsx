import { Routes, Route, Link } from 'react-router-dom'
import CaseList from './components/CaseList'
import CaseCreate from './components/CaseCreate'
import CaseDetail from './components/CaseDetail'

export default function App() {
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
          <span className="ml-auto text-xs opacity-70">v2.0 · Judge-Trustworthy</span>
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
