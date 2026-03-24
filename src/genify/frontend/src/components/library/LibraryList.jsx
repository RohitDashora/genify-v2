import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowUpDown, BookMarked, Clock, Inbox, Search } from 'lucide-react'
import { formatRelative } from 'date-fns'
import { fetchJSON } from '../../api'
import { formatCompletedLabel } from '../../utils/tableRef'
import HelpHint from '../HelpHint'
import MetadataBadges from './MetadataBadges'
import {
  ARTIFACT_STATUS_FILTER,
  ARTIFACT_STATUS_LABELS,
  FILTER_CHIP_BASE,
  FILTER_CHIP_IDLE,
  FILTER_CHIP_SELECTED,
  TYPE_LABELS,
} from './metadataLabels'

const SORT_OPTIONS = [
  { value: 'updated', label: 'Updated' },
  { value: 'name', label: 'Name' },
  { value: 'created', label: 'Created' },
]

function ListSkeleton() {
  const pulse = 'animate-pulse rounded-lg bg-gray-200/80'
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading saved metadata">
      {[1, 2, 3, 4].map((k) => (
        <div key={k} className="rounded-xl border border-border-subtle bg-surface p-2.5 shadow-card space-y-2">
          <div className={`${pulse} h-4 w-[85%]`} />
          <div className={`${pulse} h-3 w-24`} />
        </div>
      ))}
    </div>
  )
}

export default function LibraryList({ selectedId }) {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [filterTemplate, setFilterTemplate] = useState('all')
  const [artifactFilter, setArtifactFilter] = useState('all')
  const [sortMode, setSortMode] = useState('updated')

  const { data: items, isLoading, isError, error } = useQuery({
    queryKey: ['completed'],
    queryFn: () => fetchJSON('/completed'),
  })

  const templateKeys = useMemo(() => Object.keys(TYPE_LABELS), [])

  const filteredSorted = useMemo(() => {
    if (!items?.length) return []
    const q = search.trim().toLowerCase()
    let list = items.map((item) => {
      const { label, isCombined } = formatCompletedLabel(item.table_fqn, item.table_ref)
      return { ...item, _label: label, _isCombined: isCombined }
    })
    if (filterTemplate !== 'all') {
      list = list.filter((item) => item.template_type === filterTemplate)
    }
    if (artifactFilter !== 'all') {
      const pred = ARTIFACT_STATUS_FILTER[artifactFilter]
      if (pred) {
        list = list.filter((item) => pred(item.artifact_status || 'complete'))
      }
    }
    if (q) {
      list = list.filter((item) => {
        const fqn = item.table_fqn ? String(item.table_fqn).toLowerCase() : ''
        return item._label.toLowerCase().includes(q) || fqn.includes(q)
      })
    }
    const sorted = [...list].sort((a, b) => {
      if (sortMode === 'updated') {
        return new Date(b.updated_at) - new Date(a.updated_at)
      }
      if (sortMode === 'created') {
        return new Date(b.created_at) - new Date(a.created_at)
      }
      return a._label.localeCompare(b._label)
    })
    return sorted
  }, [items, search, filterTemplate, artifactFilter, sortMode])

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full max-h-full">
      <div className="shrink-0 space-y-2 pb-2 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <BookMarked className="w-5 h-5 text-brand-500 shrink-0" aria-hidden />
          <h2 className="text-base font-semibold text-gray-900">Saved metadata</h2>
          <HelpHint label="About: Saved metadata">
            Completed YAML outputs from your sessions. Click a card to view, edit, or copy.
          </HelpHint>
        </div>

        <div className="relative">
          <label htmlFor="library-search" className="sr-only">
            Search saved metadata
          </label>
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
            aria-hidden
          />
          <input
            id="library-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by table name…"
            className="w-full border border-border-subtle rounded-lg pl-9 pr-3 py-1.5 text-sm bg-surface focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            autoComplete="off"
          />
        </div>

        <div className="flex flex-col gap-2">
          <div
            className="flex min-w-0 flex-nowrap items-center gap-2 overflow-x-auto pb-0.5 -mx-0.5 px-0.5"
            role="tablist"
            aria-label="Filter by status"
          >
            <span className="hidden sm:inline text-xs text-gray-500 shrink-0">Status</span>
            {[
              { id: 'all', label: 'All' },
              { id: 'in_progress', label: 'In progress' },
              { id: 'complete', label: 'Complete' },
              { id: 'needs_attention', label: 'Needs attention' },
            ].map((chip) => (
              <button
                key={chip.id}
                type="button"
                role="tab"
                aria-selected={artifactFilter === chip.id}
                onClick={() => setArtifactFilter(chip.id)}
                className={`${FILTER_CHIP_BASE} shrink-0 ${
                  artifactFilter === chip.id ? FILTER_CHIP_SELECTED : FILTER_CHIP_IDLE
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>
          <div className="flex min-w-0 flex-nowrap items-center gap-2 overflow-x-auto pb-0.5 -mx-0.5 px-0.5">
            <span className="hidden sm:inline text-xs text-gray-500 shrink-0">Type</span>
            <button
              type="button"
              onClick={() => setFilterTemplate('all')}
              aria-pressed={filterTemplate === 'all'}
              className={`${FILTER_CHIP_BASE} shrink-0 ${
                filterTemplate === 'all' ? FILTER_CHIP_SELECTED : FILTER_CHIP_IDLE
              }`}
            >
              All
            </button>
            {templateKeys.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilterTemplate(key)}
                aria-pressed={filterTemplate === key}
                className={`${FILTER_CHIP_BASE} shrink-0 ${
                  filterTemplate === key ? FILTER_CHIP_SELECTED : FILTER_CHIP_IDLE
                }`}
              >
                {TYPE_LABELS[key]}
              </button>
            ))}
          </div>

          <div className="flex min-w-0 items-center gap-2">
            <ArrowUpDown className="w-4 h-4 text-gray-400 shrink-0" aria-hidden />
            <label htmlFor="library-sort" className="text-xs text-gray-500 shrink-0">
              Sort
            </label>
            <select
              id="library-sort"
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value)}
              className="min-w-0 flex-1 max-w-full border border-border-subtle rounded-lg px-2 py-1 text-xs bg-surface focus:ring-2 focus:ring-brand-500 focus:border-brand-500 sm:max-w-[11rem]"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto space-y-1.5 pt-2 pr-0.5" aria-label="Saved metadata list">
        {isLoading && <ListSkeleton />}

        {isError && (
          <p className="text-sm text-danger-700">Failed to load: {error?.message}</p>
        )}

        {!isLoading && !isError && items?.length === 0 && (
          <div className="rounded-xl border border-border-subtle bg-surface p-5 text-center text-sm text-gray-500">
            <Inbox className="w-10 h-10 mx-auto text-gray-300 mb-2" aria-hidden />
            <p>No saved metadata yet.</p>
            <Link to="/" className="text-brand-500 hover:underline mt-1 inline-block">
              Start a session
            </Link>
          </div>
        )}

        {!isLoading && !isError && items?.length > 0 && filteredSorted.length === 0 && (
          <p className="text-sm text-gray-500 py-4 text-center">No items match your search or filter.</p>
        )}

        {!isLoading &&
          !isError &&
          filteredSorted.map((item) => {
            const isSelected = item.id === selectedId
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => navigate(`/library/${item.id}`)}
                aria-current={isSelected ? 'true' : undefined}
                className={`w-full text-left rounded-xl border p-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ${
                  isSelected
                    ? 'border-border-subtle border-l-4 border-l-brand-500 bg-brand-50 shadow-card'
                    : 'border-border-subtle bg-surface hover:border-gray-300 shadow-card'
                }`}
              >
                <p className="text-sm font-medium text-gray-900 truncate leading-tight" title={item._label}>
                  {item._label}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <MetadataBadges templateType={item.template_type} isCombined={item._isCombined} />
                  <span
                    className={`inline-flex items-center px-1.5 py-0 rounded-full text-[10px] font-semibold border ${
                      item.artifact_status === 'complete'
                        ? 'bg-success-50 text-success-800 border-success-200/80'
                        : item.artifact_status === 'in_progress'
                          ? 'bg-brand-50 text-brand-800 border-brand-200/80'
                          : 'bg-warning-50 text-warning-900 border-warning-200/80'
                    }`}
                  >
                    {ARTIFACT_STATUS_LABELS[item.artifact_status] ||
                      ARTIFACT_STATUS_LABELS.complete}
                  </span>
                </div>
                <p className="mt-1.5 text-[11px] text-gray-400 leading-snug">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3 h-3 shrink-0 text-gray-400" aria-hidden />
                    {formatRelative(new Date(item.updated_at), new Date())}
                  </span>
                  <span className="mx-1.5 text-gray-300" aria-hidden>
                    ·
                  </span>
                  <span
                    className="inline-flex items-center align-middle px-1.5 py-0 rounded-full text-[10px] font-semibold bg-brand-50 text-brand-800 border border-brand-200/80"
                    title={`Version ${item.version}`}
                  >
                    v{item.version}
                  </span>
                  <span className="mx-1.5 text-gray-300" aria-hidden>
                    ·
                  </span>
                  <span className="text-gray-400" title={new Date(item.created_at).toISOString()}>
                    Created {formatRelative(new Date(item.created_at), new Date())}
                  </span>
                </p>
              </button>
            )
          })}
      </div>
    </div>
  )
}
