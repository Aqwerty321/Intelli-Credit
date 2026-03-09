import { Routes, Route } from 'react-router-dom'
import AppShell from './components/AppShell'
import Dashboard from './components/Dashboard'
import CaseList from './components/CaseList'
import CaseCreate from './components/CaseCreate'
import CaseDetail from './components/CaseDetail'
import CaseCompare from './components/CaseCompare'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/cases" element={<CaseList />} />
        <Route path="/cases/new" element={<CaseCreate />} />
        <Route path="/cases/compare" element={<CaseCompare />} />
        <Route path="/cases/:caseId" element={<CaseDetail />} />
      </Route>
    </Routes>
  )
}
