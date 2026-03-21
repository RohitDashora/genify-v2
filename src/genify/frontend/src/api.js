const BASE = '/api'

/**
 * @param {string} endpoint
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 * @throws {Error & { code?: string, status?: number }} — `code` set when API returns structured detail (e.g. not_waiting_for_user)
 */
export async function fetchJSON(endpoint, options = {}) {
  const res = await fetch(`${BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    let message = `HTTP ${res.status}`
    let code
    const d = body.detail
    if (typeof d === 'string') {
      message = d
    } else if (d && typeof d === 'object') {
      message = d.message ?? d.detail ?? message
      code = d.code
    }
    const err = new Error(message)
    err.code = code
    err.status = res.status
    throw err
  }
  return res.json()
}

/**
 * SSE client for the agent session stream.
 * Note: browsers may auto-reconnect EventSource on transient errors; `onerror` fires for
 * failures and reconnect attempts — do not always treat it as "session dead".
 */
export function connectSSE(sessionId, handlers) {
  const es = new EventSource(`${BASE}/sessions/${sessionId}/stream`)

  const events = [
    'status',
    'thinking',
    'plan',
    'yaml_chunk',
    'section_complete',
    'question',
    'complete',
    'error',
    'trace',
  ]
  const handlerMap = {
    status: handlers.onStatus,
    thinking: handlers.onThinking,
    plan: handlers.onPlan,
    yaml_chunk: handlers.onYamlChunk,
    section_complete: handlers.onSectionComplete,
    question: handlers.onQuestion,
    complete: handlers.onComplete,
    error: handlers.onError,
    trace: handlers.onTrace,
  }

  for (const evt of events) {
    const fn = handlerMap[evt]
    if (typeof fn !== 'function') continue
    es.addEventListener(evt, (e) => {
      try {
        fn(JSON.parse(e.data))
      } catch (err) {
        console.error(`SSE parse error for ${evt}:`, err)
      }
    })
  }

  if (typeof handlers.onOpen === 'function') {
    es.addEventListener('open', () => handlers.onOpen())
  }

  es.onerror = () => {
    if (typeof handlers.onStreamError === 'function') handlers.onStreamError(es)
    if (handlers.onDisconnect) handlers.onDisconnect(es)
  }

  return es
}
