/**
 * Frontend GNN inference via ONNX Runtime Web.
 *
 * Lazy-loads onnxruntime-web only when first called to avoid the 8MB
 * WASM bundle on initial page load.
 */

const MODEL_URL = '/models/demo_graph_gnn.onnx'
const META_URL = '/models/demo_graph_gnn_meta.json'

const GRAPH_LABELS = ['clean', 'ring', 'star_seller', 'dense_cluster', 'layered_chain']

const ROLE_TO_VALUE = {
  borrower: 1.0,
  supplier: 0.7,
  buyer: 0.5,
  related_party: 0.9,
  shell: 1.2,
  distributor: 0.6,
  bank: 0.2,
  customer: 0.4,
}

let _ort = null
let _session = null
let _meta = null

async function ensureSession() {
  if (_session) return _session
  // Lazy-load onnxruntime-web.
  // With optimizeDeps.exclude in vite.config.js, Vite serves ORT's
  // .mjs glue and .wasm binaries directly from node_modules — no
  // need to copy them to public/ or set wasmPaths.
  _ort = await import('onnxruntime-web')

  // Fall back to single-threaded WASM if SharedArrayBuffer is not available
  // (cross-origin isolation not configured).
  if (typeof SharedArrayBuffer === 'undefined') {
    _ort.env.wasm.numThreads = 1
  }

  const metaRes = await fetch(META_URL)
  _meta = await metaRes.json()

  _session = await _ort.InferenceSession.create(MODEL_URL, {
    executionProviders: ['wasm'],
  })
  return _session
}

/**
 * Build GCNConv-compatible normalized adjacency matrix from edge_index.
 * Replicates PyG's GCNConv normalization:
 * 1. Add self-loops
 * 2. Compute degree from A_hat (counting dst)
 * 3. adj[dst, src] = d_inv_sqrt[dst] * d_inv_sqrt[src]
 */
function buildNormalizedAdjacency(edgeIndex, numNodes) {
  const [srcs, dsts] = edgeIndex
  // Build combined edge list with self-loops
  const allSrcs = [...srcs]
  const allDsts = [...dsts]
  for (let i = 0; i < numNodes; i++) {
    allSrcs.push(i)
    allDsts.push(i)
  }
  // Compute degree (count edges into each dst node)
  const deg = new Float32Array(numNodes)
  for (let i = 0; i < allSrcs.length; i++) {
    deg[allDsts[i]] += 1.0
  }
  const dInvSqrt = new Float32Array(numNodes)
  for (let i = 0; i < numNodes; i++) {
    dInvSqrt[i] = deg[i] > 0 ? Math.pow(deg[i], -0.5) : 0
  }
  // Fill adjacency: adj[dst, src] += d_inv_sqrt[dst] * d_inv_sqrt[src]
  const adj = new Float32Array(numNodes * numNodes)
  for (let i = 0; i < allSrcs.length; i++) {
    const src = allSrcs[i]
    const dst = allDsts[i]
    adj[dst * numNodes + src] += dInvSqrt[dst] * dInvSqrt[src]
  }
  return adj
}

/**
 * Compute 7-dim node features from a transaction list.
 * transactions: [{ source, target, amount, source_role, target_role }]
 */
export function computeFeatures(transactions) {
  const nodeIndex = {}
  const incoming = {}
  const outgoing = {}
  const inValue = {}
  const outValue = {}
  const roles = {}
  let nextIdx = 0

  for (const txn of transactions) {
    for (const [key, roleKey] of [['source', 'source_role'], ['target', 'target_role']]) {
      const node = txn[key]
      if (!(node in nodeIndex)) {
        nodeIndex[node] = nextIdx++
        incoming[node] = 0
        outgoing[node] = 0
        inValue[node] = 0
        outValue[node] = 0
        roles[node] = txn[roleKey] || 'unknown'
      }
    }
    const amount = parseFloat(txn.amount || 0)
    outgoing[txn.source]++
    incoming[txn.target]++
    outValue[txn.source] += amount
    inValue[txn.target] += amount
  }

  const numNodes = Object.keys(nodeIndex).length
  const nodeNames = new Array(numNodes)
  for (const [name, idx] of Object.entries(nodeIndex)) nodeNames[idx] = name

  const features = new Float32Array(numNodes * 7)
  for (let i = 0; i < numNodes; i++) {
    const node = nodeNames[i]
    const inDeg = incoming[node]
    const outDeg = outgoing[node]
    const inAmt = inValue[node] / 1_000_000
    const outAmt = outValue[node] / 1_000_000
    features[i * 7 + 0] = inDeg
    features[i * 7 + 1] = outDeg
    features[i * 7 + 2] = inAmt
    features[i * 7 + 3] = outAmt
    features[i * 7 + 4] = inAmt - outAmt
    features[i * 7 + 5] = inAmt + outAmt
    features[i * 7 + 6] = ROLE_TO_VALUE[roles[node]] || 0
  }

  const edgeSrcs = []
  const edgeDsts = []
  for (const txn of transactions) {
    edgeSrcs.push(nodeIndex[txn.source])
    edgeDsts.push(nodeIndex[txn.target])
  }

  return { features, edgeIndex: [edgeSrcs, edgeDsts], numNodes, nodeNames }
}

/**
 * Run GNN inference on features + edge_index.
 * Returns { label, probabilities: { clean: 0.x, ring: 0.x, ... } }
 */
export async function infer(features, edgeIndex, numNodes) {
  const session = await ensureSession()
  const adj = buildNormalizedAdjacency(edgeIndex, numNodes)

  const featuresTensor = new _ort.Tensor('float32', features, [numNodes, 7])
  const adjTensor = new _ort.Tensor('float32', adj, [numNodes, numNodes])

  const results = await session.run({
    node_features: featuresTensor,
    adjacency: adjTensor,
  })

  const logits = results.logits.data
  // Softmax
  const maxVal = Math.max(...logits)
  const exps = Array.from(logits).map(v => Math.exp(v - maxVal))
  const sumExps = exps.reduce((a, b) => a + b, 0)
  const probs = exps.map(e => e / sumExps)

  const probabilities = {}
  let maxIdx = 0
  for (let i = 0; i < GRAPH_LABELS.length; i++) {
    probabilities[GRAPH_LABELS[i]] = Math.round(probs[i] * 10000) / 10000
    if (probs[i] > probs[maxIdx]) maxIdx = i
  }

  return {
    label: GRAPH_LABELS[maxIdx],
    probabilities,
  }
}

/**
 * Full inference from a transaction list (combine feature computation + model inference).
 */
export async function inferFromTransactions(transactions) {
  const { features, edgeIndex, numNodes, nodeNames } = computeFeatures(transactions)
  const result = await infer(features, edgeIndex, numNodes)
  return { ...result, nodeNames, numNodes }
}

/**
 * What-if: modify a transaction and re-infer.
 */
export async function whatIf(transactions, modification) {
  const modified = transactions.map(t => ({ ...t }))
  if (modification.removeIndex != null) {
    modified.splice(modification.removeIndex, 1)
  }
  if (modification.addTransaction) {
    modified.push(modification.addTransaction)
  }
  if (modification.modifyIndex != null && modification.changes) {
    Object.assign(modified[modification.modifyIndex], modification.changes)
  }
  return inferFromTransactions(modified)
}
