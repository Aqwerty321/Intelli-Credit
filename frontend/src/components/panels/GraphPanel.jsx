import { useState, useEffect, useRef } from 'react'
import { getGraphTopology } from '../../services/api'
import ForceGraph from '../charts/ForceGraph'
import ClassRadar from '../charts/ClassRadar'
import GraphPlayground from '../charts/GraphPlayground'

export default function GraphPanel({ caseId, graphTrace }) {
  const [topology, setTopology] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const containerRef = useRef(null)
  const [width, setWidth] = useState(700)

  useEffect(() => {
    if (!caseId) return
    setLoading(true)
    setError('')
    getGraphTopology(caseId)
      .then(setTopology)
      .catch(e => setError(e.message || 'Failed to load graph'))
      .finally(() => setLoading(false))
  }, [caseId])

  // Responsive width
  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        setWidth(Math.max(400, entry.contentRect.width - 24))
      }
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  if (loading) {
    return <p className="text-sm text-slate-400 py-8 text-center">Loading graph topology…</p>
  }

  if (error) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded px-3 py-3 text-sm text-amber-700">
        {error}
      </div>
    )
  }

  const nodes = topology?.nodes || []
  const edges = topology?.edges || []
  const fraudAlerts = topology?.fraud_alerts || []
  const gnnLabel = topology?.gnn_label || graphTrace?.gnn_label || 'clean'
  const classProbabilities = topology?.class_probabilities || graphTrace?.class_probabilities || {}
  const transactions = graphTrace?.graph_transactions || []
  const isSynthesized = graphTrace?.evidence_source === 'synthesized_from_facts'

  return (
    <div ref={containerRef} className="space-y-3">
      {isSynthesized && (
        <div className="bg-blue-50 border border-blue-200 rounded px-3 py-2 text-xs text-blue-700">
          <span className="font-semibold">Synthesized graph</span> — cash-flow topology generated from domain facts (turnover, bank credits, promoters). Upload transaction documents for real transaction analysis.
        </div>
      )}
      {/* Force-directed network graph */}
      <ForceGraph
        nodes={nodes}
        edges={edges}
        fraudAlerts={fraudAlerts}
        gnnLabel={gnnLabel}
        width={width}
        height={Math.min(500, Math.max(350, nodes.length * 40))}
      />

      {/* Side-by-side: Radar + Playground */}
      <div className="grid lg:grid-cols-2 gap-3">
        <ClassRadar classProbabilities={classProbabilities} />
        <GraphPlayground transactions={transactions} />
      </div>
    </div>
  )
}
