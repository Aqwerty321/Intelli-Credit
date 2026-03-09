import { describe, it, expect } from 'vitest'
import { computeFeatures } from '../services/gnn'

const TRANSACTIONS = [
  { source: 'A', target: 'B', amount: 1000000, source_role: 'borrower', target_role: 'supplier' },
  { source: 'B', target: 'C', amount: 500000, source_role: 'supplier', target_role: 'buyer' },
  { source: 'C', target: 'A', amount: 800000, source_role: 'buyer', target_role: 'borrower' },
]

describe('computeFeatures', () => {
  it('returns correct number of nodes', () => {
    const { numNodes, nodeNames } = computeFeatures(TRANSACTIONS)
    expect(numNodes).toBe(3)
    expect(nodeNames).toHaveLength(3)
    expect(nodeNames).toContain('A')
    expect(nodeNames).toContain('B')
    expect(nodeNames).toContain('C')
  })

  it('returns 7-dim feature vector per node', () => {
    const { features, numNodes } = computeFeatures(TRANSACTIONS)
    expect(features).toBeInstanceOf(Float32Array)
    expect(features.length).toBe(numNodes * 7)
  })

  it('computes correct edge index', () => {
    const { edgeIndex } = computeFeatures(TRANSACTIONS)
    const [srcs, dsts] = edgeIndex
    expect(srcs).toHaveLength(3)
    expect(dsts).toHaveLength(3)
  })

  it('handles single transaction', () => {
    const { numNodes, nodeNames } = computeFeatures([
      { source: 'X', target: 'Y', amount: 100, source_role: 'supplier', target_role: 'buyer' },
    ])
    expect(numNodes).toBe(2)
    expect(nodeNames).toContain('X')
    expect(nodeNames).toContain('Y')
  })

  it('handles empty transactions', () => {
    const { numNodes, features, edgeIndex } = computeFeatures([])
    expect(numNodes).toBe(0)
    expect(features.length).toBe(0)
    expect(edgeIndex[0]).toHaveLength(0)
  })

  it('assigns correct role values', () => {
    const result = computeFeatures([
      { source: 'A', target: 'B', amount: 1000000, source_role: 'borrower', target_role: 'shell' },
    ])
    const idxA = result.nodeNames.indexOf('A')
    const idxB = result.nodeNames.indexOf('B')
    // feature[6] = role_to_value. borrower=1.0, shell=1.2
    expect(result.features[idxA * 7 + 6]).toBeCloseTo(1.0, 2)
    expect(result.features[idxB * 7 + 6]).toBeCloseTo(1.2, 2)
  })

  it('scales amounts to millions', () => {
    const result = computeFeatures([
      { source: 'P', target: 'Q', amount: 2000000, source_role: 'supplier', target_role: 'buyer' },
    ])
    const idxP = result.nodeNames.indexOf('P')
    // feature[3] = outgoing value / 1M = 2.0
    expect(result.features[idxP * 7 + 3]).toBeCloseTo(2.0, 2)
    // feature[2] = incoming value = 0
    expect(result.features[idxP * 7 + 2]).toBeCloseTo(0, 2)
  })
})
