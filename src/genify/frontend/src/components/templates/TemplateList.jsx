import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowUpDown,
  Clock,
  Hash,
  Inbox,
  LayoutTemplate,
  Plus,
  Search,
  Star,
} from 'lucide-react'
import { formatRelative } from 'date-fns'
import { fetchJSON } from '../../api'
import HelpHint from '../HelpHint'
import {
  FILTER_CHIP_BASE,
  FILTER_CHIP_IDLE,
  FILTER_CHIP_SELECTED,
  TYPE_LABELS,
  templateLabel,
} from '../library/metadataLabels'

const SORT_OPTIONS = [
  { value: 'version', label: 'Version' },
  { value: 'updated', label: 'Updated' },
  { value: 'name', label: 'Name' },
]

function ListSkeleton() {
  const pulse = 'animate-pulse rounded-lg bg-gray-200/80'
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading templates">
      {[1, 2, 3, 4].map((k) => (
        <div key={k} className="rounded-xl border border-border-subtle bg-surface p-2.5 shadow-card space-y-2">
          <div className={`${pulse} h-4 w-[85%]`} />
          <div className={`${pulse} h-3 w-24`} />
        </div>
      ))}
    </div>
  )
}

export default function TemplateList({ selectedId }) {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [filterTemplate, setFilterTemplate] = useState('all')
  const [sortMode, setSortMode] = useState('version')

  const { data: items, isLoading, isError, error } = useQuery({
    queryKey: ['templates'],
    queryFn: () => fetchJSON('/templates'),
  })

  const typeKeys = useMemo(() => {
    const fromApi = new Set()
    items?.forEach((row) => fromApi.add(row.type))
    Object.keys(TYPE_LABELS).forEach((k) => fromApi.add(k))
    return Array.from(fromApi).sort()
  }, [items])

  const filteredSorted = useMemo(() => {
    if (!items?.length) return []
    const q = search.trim().toLowerCase()
    let list = [...items]
    if (filterTemplate !== 'all') {
      list = list.filter((item) => item.type === filterTemplate)
    }
    if (q) {
      list = list.filter((item) => {
        const hay = [
          item.name,
          item.type,
          item.notes,
          String(item.version),
          templateLabel(item.type),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        return hay.includes(q)
      })
    }
    const sorted = [...list].sort((a, b) => {
      if (sortMode === 'version') {
        if (a.type !== b.type) return a.type.localeCompare(b.type)
        return b.version - a.version
      }
      if (sortMode === 'updated') {
        return new Date(b.updated_at) - new Date(a.updated_at)
      }
      return (a.name || '').localeCompare(b.name || '')
    })
    return sorted
  }, [items, search, filterTemplate, sortMode])

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full max-h-full">
      <div className="shrink-0 space-y-2 pb-2 border-b border-border-subtle">
        <div className="flex items-center gap-2 flex-wrap">
          <LayoutTemplate className="w-5 h-5 text-brand-500 shrink-0" aria-hidden />
          <h2 className="text-base font-semibold text-gray-900">Templates</h2>
          <HelpHint label="About: Templates">
            Versions live in Lakebase. New sessions use the <strong>default</strong> version for each
            template type.
          </HelpHint>
          <button
            type="button"
            onClick={() => navigate('/templates/new')}
            className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-brand-500 text-white hover:bg-brand-600 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
          >
            <Plus className="w-3.5 h-3.5" aria-hidden />
            New version
          </button>
        </div>

        <div className="relative">
          <label htmlFor="templates-search" className="sr-only">
            Search templates
          </label>
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
            aria-hidden
          />
          <input
            id="templates-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, type, version…"
            className="w-full border border-border-subtle rounded-lg pl-9 pr-3 py-1.5 text-sm bg-surface focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            autoComplete="off"
          />
        </div>

        <div className="flex flex-col gap-2">
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
            {typeKeys.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilterTemplate(key)}
                aria-pressed={filterTemplate === key}
                className={`${FILTER_CHIP_BASE} shrink-0 ${
                  filterTemplate === key ? FILTER_CHIP_SELECTED : FILTER_CHIP_IDLE
                }`}
              >
                {templateLabel(key)}
              </button>
            ))}
          </div>

          <div className="flex min-w-0 items-center gap-2">
            <ArrowUpDown className="w-4 h-4 text-gray-400 shrink-0" aria-hidden />
            <label htmlFor="templates-sort" className="text-xs text-gray-500 shrink-0">
              Sort
            </label>
            <select
              id="templates-sort"
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

      <div className="flex-1 min-h-0 overflow-y-auto space-y-1.5 pt-2 pr-0.5" aria-label="Template versions list">
        {isLoading && <ListSkeleton />}

        {isError && (
          <p className="text-sm text-danger-700">Failed to load: {error?.message}</p>
        )}

        {!isLoading && !isError && items?.length === 0 && (
          <div className="rounded-xl border border-border-subtle bg-surface p-5 text-center text-sm text-gray-500">
            <Inbox className="w-10 h-10 mx-auto text-gray-300 mb-2" aria-hidden />
            <p>No template versions yet.</p>
            <Link to="/templates/new" className="text-brand-500 hover:underline mt-1 inline-block">
              Create template
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
            const title = `${templateLabel(item.type)} · v${item.version}`
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => navigate(`/templates/${item.id}`)}
                aria-current={isSelected ? 'true' : undefined}
                className={`w-full text-left rounded-xl border p-2.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ${
                  isSelected
                    ? 'border-border-subtle border-l-4 border-l-brand-500 bg-brand-50 shadow-card'
                    : 'border-border-subtle bg-surface hover:border-gray-300 shadow-card'
                }`}
              >
                <p className="text-sm font-medium text-gray-900 truncate leading-tight" title={title}>
                  {title}
                </p>
                <p className="text-xs text-gray-600 mt-0.5 truncate" title={item.name}>
                  {item.name}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  {item.is_active && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0 rounded-full text-[10px] font-semibold bg-brand-50 text-brand-800 border border-brand-200/80">
                      <Star className="w-3 h-3" aria-hidden />
                      Default
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-[11px] text-gray-400 leading-snug">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3 h-3 shrink-0 text-gray-400" aria-hidden />
                    {formatRelative(new Date(item.updated_at), new Date())}
                  </span>
                  <span className="mx-1.5 text-gray-300" aria-hidden>
                    ·
                  </span>
                  <span className="inline-flex items-center gap-0.5 text-gray-500">
                    <Hash className="w-3 h-3 shrink-0" aria-hidden />
                    v{item.version}
                  </span>
                </p>
              </button>
            )
          })}
      </div>
    </div>
  )
}
