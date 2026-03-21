import { useState, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { Loader2, RefreshCw, BellRing } from 'lucide-react'
import { fetchJSON } from '../api'
import ConfirmDialog from './ConfirmDialog'
import HelpHint from './HelpHint'

const STATUS_COLORS = {
  created: 'bg-gray-100 text-gray-600',
  executing: 'bg-blue-100 text-blue-700',
  waiting_for_user: 'bg-amber-100 text-amber-900 ring-2 ring-amber-300',
  complete: 'bg-success-100 text-success-700',
  failed: 'bg-danger-100 text-danger-800',
}

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'needs_you', label: 'Needs you' },
  { id: 'running', label: 'Running' },
  { id: 'done', label: 'Done' },
]

export default function SessionList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteError, setDeleteError] = useState(null)
  const [filter, setFilter] = useState('all')
  const [pendingDeleteId, setPendingDeleteId] = useState(null)

  const {
    data: sessions = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => fetchJSON('/sessions'),
  })

  const filteredSessions = useMemo(() => {
    if (filter === 'all') return sessions
    if (filter === 'needs_you')
      return sessions.filter((s) => s.status === 'waiting_for_user')
    if (filter === 'running')
      return sessions.filter((s) =>
        ['created', 'executing'].includes(s.status),
      )
    if (filter === 'done')
      return sessions.filter((s) =>
        ['complete', 'failed'].includes(s.status),
      )
    return sessions
  }, [sessions, filter])

  const handleDeleteClick = (sid) => {
    setPendingDeleteId(sid)
  }

  const confirmDelete = async () => {
    if (!pendingDeleteId) return
    const sid = pendingDeleteId
    setPendingDeleteId(null)
    setDeleteError(null)
    try {
      await fetchJSON(`/sessions/${sid}`, { method: 'DELETE' })
      queryClient.setQueryData(['sessions'], (prev) =>
        Array.isArray(prev) ? prev.filter((s) => s.id !== sid) : prev,
      )
    } catch (e) {
      setDeleteError(e.message || 'Delete failed')
    }
  }

  const tableLabel = (ref) => {
    if (!ref) return '—'
    if (ref.table) return `${ref.catalog}.${ref.schema}.${ref.table}`
    if (ref.tables) return `${ref.catalog}.${ref.schema}.* (${ref.tables.length} tables)`
    return `${ref.catalog || ''}.${ref.schema || ''}`
  }

  const relativeTime = (iso) => {
    if (!iso) return ''
    try {
      return formatDistanceToNow(new Date(iso), { addSuffix: true })
    } catch {
      return ''
    }
  }

  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-5 shadow-card">
      <div className="flex items-center justify-between mb-4 gap-2 flex-wrap">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          Your Sessions
          <HelpHint label="About: Your Sessions">
            Your past and active sessions. Click to resume an in-progress session or review a completed one.
          </HelpHint>
        </h2>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="text-xs text-gray-500 hover:text-gray-700 inline-flex items-center gap-1 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} aria-hidden />
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4" role="tablist" aria-label="Filter sessions">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={filter === f.id}
            onClick={() => setFilter(f.id)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              filter === f.id
                ? 'bg-brand-500 text-white border-brand-500'
                : 'bg-gray-50 text-gray-600 border-border-subtle hover:border-gray-300'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-gray-400 text-sm py-6">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
          Loading sessions…
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 text-danger-800 text-sm p-3 mb-3">
          <p className="font-medium">Could not load sessions</p>
          <p className="mt-1">{error?.message || 'Unknown error'}</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="mt-2 text-xs underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {deleteError && (
        <div className="rounded-lg border border-amber-200 bg-warning-50 text-warning-800 text-sm p-3 mb-3">
          {deleteError}
          <button
            type="button"
            onClick={() => setDeleteError(null)}
            className="ml-2 text-xs underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {!isLoading && !isError && sessions.length === 0 && (
        <p className="text-sm text-gray-400 py-4">No sessions yet. Select tables and start one.</p>
      )}

      {!isLoading && !isError && sessions.length > 0 && filteredSessions.length === 0 && (
        <p className="text-sm text-gray-500 py-4">No sessions in this filter.</p>
      )}

      {!isLoading && !isError && filteredSessions.length > 0 && (
        <div className="space-y-3">
          {filteredSessions.map((s) => {
            const waiting = s.status === 'waiting_for_user'
            return (
              <div
                key={s.id}
                className={`border rounded-lg p-3 ${
                  waiting
                    ? 'border-l-4 border-l-amber-500 border-amber-200 bg-amber-50/40'
                    : 'border-gray-100'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">{tableLabel(s.table_ref)}</div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <span className="text-xs text-gray-400 capitalize">
                        {s.template_type.replace('_', ' ')}
                      </span>
                      <span className="text-xs text-gray-300" aria-hidden>
                        |
                      </span>
                      <span className="text-xs text-gray-400">{s.mode.replace('_', ' ')}</span>
                      {s.updated_at && (
                        <>
                          <span className="text-xs text-gray-300" aria-hidden>
                            |
                          </span>
                          <span className="text-xs text-gray-400">{relativeTime(s.updated_at)}</span>
                        </>
                      )}
                    </div>
                    {waiting && (
                      <p className="mt-2 text-xs font-medium text-amber-900 inline-flex items-center gap-1">
                        <BellRing className="w-3.5 h-3.5 shrink-0" aria-hidden />
                        Action needed — open to answer the agent
                      </p>
                    )}
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 ${STATUS_COLORS[s.status] || 'bg-gray-100'}`}
                  >
                    {s.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => navigate(`/session/${s.id}`)}
                    className="text-xs px-3 py-1 rounded-md bg-brand-500 text-white hover:bg-brand-600"
                  >
                    {s.status === 'complete'
                      ? 'View'
                      : s.status === 'waiting_for_user'
                        ? 'Resume'
                        : 'Open'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(s.id)}
                    className="text-xs px-3 py-1 rounded-md border border-border-subtle text-gray-500 hover:border-red-300 hover:text-red-500"
                  >
                    Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        open={pendingDeleteId != null}
        title="Delete session?"
        description="This removes the session from your list. Generated YAML in Completed is not deleted."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        danger
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  )
}
