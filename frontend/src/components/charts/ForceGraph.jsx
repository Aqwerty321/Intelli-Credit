import { useRef, useEffect, useState, useCallback } from 'react'
import * as d3 from 'd3'

const ROLE_COLORS = {
  borrower: '#ef4444',
  supplier: '#3b82f6',
  buyer: '#22c55e',
  related_party: '#f59e0b',
  shell: '#dc2626',
  distributor: '#8b5cf6',
  bank: '#06b6d4',
  customer: '#10b981',
  unknown: '#94a3b8',
}

const SEVERITY_STROKE = {
  CRITICAL: '#ef4444',
  HIGH: '#f59e0b',
  MEDIUM: '#3b82f6',
  LOW: '#94a3b8',
}

function nodeRadius(node) {
  const base = 8
  const pr = (node.pagerank || 0) * 200
  return Math.max(base, Math.min(base + pr, 28))
}

export default function ForceGraph({ nodes = [], edges = [], fraudAlerts = [], gnnLabel = 'clean', width = 700, height = 500 }) {
  const svgRef = useRef(null)
  const tooltipRef = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)

  // Build cycle entity sets for highlighting
  const cycleEntities = new Set()
  fraudAlerts.filter(a => a.type === 'cycle').forEach(a => (a.entities || []).forEach(e => cycleEntities.add(e)))

  const draw = useCallback(() => {
    if (!svgRef.current || !nodes.length) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const g = svg.append('g')

    // Zoom
    const zoom = d3.zoom().scaleExtent([0.3, 5]).on('zoom', (e) => g.attr('transform', e.transform))
    svg.call(zoom)

    // Arrow markers
    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#94a3b8')

    defs.append('marker')
      .attr('id', 'arrow-cycle')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#ef4444')

    // Glow filter for fraud nodes
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'glow')
    filter.append('feMerge').selectAll('feMergeNode')
      .data(['glow', 'SourceGraphic']).enter()
      .append('feMergeNode').attr('in', d => d)

    // Max weight for scaling
    const maxWeight = d3.max(edges, d => d.weight) || 1

    // Build simulation data
    const simNodes = nodes.map(n => ({ ...n }))
    const nodeMap = new Map(simNodes.map(n => [n.id, n]))
    const simEdges = edges
      .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map(e => ({ ...e, source: e.source, target: e.target }))

    const simulation = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink(simEdges).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 4))

    // Edges
    const link = g.append('g')
      .selectAll('line')
      .data(simEdges)
      .enter().append('line')
      .attr('stroke', d => {
        const isCycle = cycleEntities.has(d.source.id || d.source) && cycleEntities.has(d.target.id || d.target)
        return isCycle ? '#ef4444' : '#cbd5e1'
      })
      .attr('stroke-width', d => Math.max(1, Math.min(5, (d.weight / maxWeight) * 5)))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', d => {
        const isCycle = cycleEntities.has(d.source.id || d.source) && cycleEntities.has(d.target.id || d.target)
        return isCycle ? 'url(#arrow-cycle)' : 'url(#arrow)'
      })

    // Weight labels
    const edgeLabels = g.append('g')
      .selectAll('text')
      .data(simEdges)
      .enter().append('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', '9px')
      .attr('fill', '#94a3b8')
      .text(d => d.weight >= 100000 ? `₹${(d.weight / 100000).toFixed(1)}L` : `₹${(d.weight / 1000).toFixed(0)}K`)

    // Nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(simNodes)
      .enter().append('circle')
      .attr('r', d => nodeRadius(d))
      .attr('fill', d => ROLE_COLORS[d.role] || ROLE_COLORS.unknown)
      .attr('stroke', d => cycleEntities.has(d.id) ? '#ef4444' : '#fff')
      .attr('stroke-width', d => cycleEntities.has(d.id) ? 3 : 1.5)
      .attr('filter', d => cycleEntities.has(d.id) ? 'url(#glow)' : null)
      .attr('cursor', 'pointer')
      .on('click', (_, d) => setSelectedNode(d))
      .on('mouseenter', (event, d) => {
        const tt = d3.select(tooltipRef.current)
        tt.style('display', 'block')
          .style('left', `${event.offsetX + 10}px`)
          .style('top', `${event.offsetY - 10}px`)
          .html(`
            <strong>${d.id}</strong><br/>
            Role: ${d.role}<br/>
            PageRank: ${(d.pagerank || 0).toFixed(4)}<br/>
            Betweenness: ${(d.betweenness || 0).toFixed(4)}<br/>
            In/Out: ${d.in_degree}/${d.out_degree}
          `)
      })
      .on('mouseleave', () => {
        d3.select(tooltipRef.current).style('display', 'none')
      })
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x; d.fy = d.y
        })
        .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null; d.fy = null
        }))

    // Node labels
    const labels = g.append('g')
      .selectAll('text')
      .data(simNodes)
      .enter().append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => nodeRadius(d) + 12)
      .attr('font-size', '10px')
      .attr('fill', '#334155')
      .attr('pointer-events', 'none')
      .text(d => d.id.length > 16 ? d.id.slice(0, 14) + '…' : d.id)

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      edgeLabels
        .attr('x', d => (d.source.x + d.target.x) / 2)
        .attr('y', d => (d.source.y + d.target.y) / 2 - 4)
      node.attr('cx', d => d.x).attr('cy', d => d.y)
      labels.attr('x', d => d.x).attr('y', d => d.y)
    })
  }, [nodes, edges, fraudAlerts, width, height, cycleEntities])

  useEffect(() => { draw() }, [draw])

  if (!nodes.length) {
    return (
      <div className="flex items-center justify-center h-64 bg-slate-50 rounded border border-slate-200">
        <p className="text-sm text-slate-400">No graph topology available — run the pipeline first</p>
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Legend */}
      <div className="absolute top-2 left-2 bg-white/90 backdrop-blur rounded border border-slate-200 px-2 py-1.5 text-[10px] z-10 space-y-0.5">
        <p className="font-semibold text-slate-600 mb-1">Node Roles</p>
        {Object.entries(ROLE_COLORS).filter(([k]) => k !== 'unknown').map(([role, color]) => (
          <div key={role} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color }} />
            <span className="capitalize">{role.replace('_', ' ')}</span>
          </div>
        ))}
        {cycleEntities.size > 0 && (
          <>
            <div className="border-t border-slate-200 my-1" />
            <div className="flex items-center gap-1.5 text-red-600 font-semibold">
              <span className="w-2.5 h-2.5 rounded-full inline-block border-2 border-red-500 bg-transparent" />
              Cycle entity
            </div>
          </>
        )}
      </div>

      {/* GNN label badge */}
      <div className="absolute top-2 right-2 z-10">
        <span className={`text-[11px] font-bold px-2 py-1 rounded ${
          gnnLabel === 'clean' ? 'bg-green-100 text-green-700' :
          gnnLabel === 'ring' ? 'bg-red-100 text-red-700' :
          'bg-amber-100 text-amber-700'
        }`}>GNN: {gnnLabel}</span>
      </div>

      <div className="relative">
        <svg ref={svgRef} width={width} height={height} className="bg-slate-50 rounded border border-slate-200" />
        <div
          ref={tooltipRef}
          className="absolute bg-slate-800 text-white text-[11px] px-2 py-1.5 rounded pointer-events-none"
          style={{ display: 'none', zIndex: 20 }}
        />
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div className="mt-2 bg-white border border-slate-200 rounded px-3 py-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-slate-700">{selectedNode.id}</h4>
            <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-slate-600 text-xs">✕</button>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-1.5 text-[11px]">
            <div><span className="text-slate-400">Role:</span> <span className="font-medium capitalize">{selectedNode.role}</span></div>
            <div><span className="text-slate-400">In:</span> {selectedNode.in_degree} <span className="text-slate-400">Out:</span> {selectedNode.out_degree}</div>
            <div><span className="text-slate-400">PageRank:</span> {(selectedNode.pagerank || 0).toFixed(4)}</div>
            <div><span className="text-slate-400">Hub:</span> {(selectedNode.hub_score || 0).toFixed(4)}</div>
            <div><span className="text-slate-400">Authority:</span> {(selectedNode.authority_score || 0).toFixed(4)}</div>
            <div><span className="text-slate-400">Betweenness:</span> {(selectedNode.betweenness || 0).toFixed(4)}</div>
          </div>
          {cycleEntities.has(selectedNode.id) && (
            <p className="text-[11px] text-red-600 mt-1.5 bg-red-50 px-2 py-0.5 rounded">⚠ Part of detected circular trading cycle</p>
          )}
        </div>
      )}
    </div>
  )
}
