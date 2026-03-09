/**
 * Centralised API client for Intelli-Credit.
 * Every function is async and throws { status, message } on non-ok responses.
 */

async function _request(method, path, body) {
  const opts = { method, headers: {} }
  if (body instanceof FormData) {
    opts.body = body
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(path, opts)
  if (!res.ok) {
    let message = res.statusText
    try { message = (await res.json()).detail || message } catch (_) {}
    const err = new Error(message)
    err.status = res.status
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Cases ────────────────────────────────────────────────────────────────────

export const listCases = () =>
  _request('GET', '/api/cases/')

export const createCase = (payload) =>
  _request('POST', '/api/cases/', payload)

export const getCase = (caseId) =>
  _request('GET', `/api/cases/${caseId}`)

export const deleteCase = (caseId) =>
  _request('DELETE', `/api/cases/${caseId}`)

// ── Documents ────────────────────────────────────────────────────────────────

export const uploadDocument = (caseId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return _request('POST', `/api/cases/${caseId}/documents`, fd)
}

/** Returns the URL to use as an <a href> for CAM download — not a fetch. */
export const downloadCAMUrl = (caseId) =>
  `/api/cases/${caseId}/cam`

// ── Notes ─────────────────────────────────────────────────────────────────────

export const listNotes = (caseId) =>
  _request('GET', `/api/cases/${caseId}/notes`)

export const addNote = (caseId, payload) =>
  _request('POST', `/api/cases/${caseId}/notes`, payload)

export const updateNote = (caseId, noteId, patch) =>
  _request('PATCH', `/api/cases/${caseId}/notes/${noteId}`, patch)

export const deleteNote = (caseId, noteId) =>
  _request('DELETE', `/api/cases/${caseId}/notes/${noteId}`)

// ── Run ──────────────────────────────────────────────────────────────────────

/** Synchronous (blocking) pipeline run. Returns { recommendation, risk_score, ... }. */
export const runSync = (caseId) =>
  _request('POST', `/api/run/${caseId}`)

/** Returns an EventSource URL (not created here — caller uses `new EventSource(url)`). */
export const streamRunUrl = (caseId) =>
  `/api/run/${caseId}/stream`

// ── AutoFetch ────────────────────────────────────────────────────────────────

/** Check if facts.md already exists for a case. */
export const checkFactsExist = (caseId) =>
  _request('GET', `/api/autofetch/${caseId}/check`)

/** Returns an EventSource URL for autofetch streaming. */
export const autofetchStreamUrl = (caseId, force = false) =>
  `/api/autofetch/${caseId}/stream?force=${force}`

// ── Health ───────────────────────────────────────────────────────────────────

export const getHealth = () =>
  _request('GET', '/api/health')
// ── Graph ────────────────────────────────────────────────────────────────

export const getGraphTopology = (caseId) =>
  _request('GET', `/api/cases/${caseId}/graph`)

export const getGraphFeatures = (caseId) =>
  _request('GET', `/api/cases/${caseId}/graph/features`)

// ── Dashboard ────────────────────────────────────────────────────────────────

export const getDashboardStats = () =>
  _request('GET', '/api/cases/stats/dashboard')

// ── Compare ──────────────────────────────────────────────────────────────────

export const compareCases = (caseIds) =>
  _request('GET', `/api/cases/compare/bulk?ids=${caseIds.join(',')}`)

// ── PDF CAM ──────────────────────────────────────────────────────────────────

export const downloadCAMPdfUrl = (caseId) =>
  `/api/cases/${caseId}/cam/pdf`