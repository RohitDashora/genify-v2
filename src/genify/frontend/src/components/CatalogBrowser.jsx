import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Loader2 } from 'lucide-react'
import { fetchJSON } from '../api'
import HelpHint from './HelpHint'

/** Split on first underscore only (e.g. MATERIALIZED_VIEW → two lines; MANAGED → one). */
function tableTypePillLines(type) {
  if (type == null || type === '') return ['', '']
  const s = String(type).trim().toUpperCase()
  const i = s.indexOf('_')
  if (i === -1) return [s, '']
  return [s.slice(0, i), s.slice(i + 1)]
}

function TableTypePill({ type }) {
  const [line1, line2] = tableTypePillLines(type)
  if (!line1) return null
  return (
    <span
      className="shrink-0 inline-flex min-w-[3rem] max-w-[4.75rem] flex-col items-center justify-center rounded-md border border-gray-200 bg-gray-50 px-1 py-1 text-center leading-[1.1] text-[9px] font-semibold uppercase tracking-wide text-gray-500"
      title={type ? String(type) : undefined}
    >
      <span className="break-words hyphens-auto">{line1}</span>
      {line2 ? <span className="break-words hyphens-auto">{line2}</span> : null}
    </span>
  )
}

function SkeletonRows({ n = 6 }) {
  return (
    <div className="border border-border-subtle rounded-lg overflow-hidden divide-y divide-gray-100">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-3 animate-pulse">
          <div className="mt-0.5 h-4 w-4 shrink-0 rounded bg-gray-200" />
          <div className="flex-1 min-w-0 space-y-2">
            <div className="h-4 bg-gray-200 rounded max-w-xs" />
            <div className="h-3 bg-gray-100 rounded w-full" />
          </div>
          <div className="h-10 w-12 shrink-0 rounded-md bg-gray-100" />
        </div>
      ))}
    </div>
  )
}

export default function CatalogBrowser({ onSelect }) {
  const [selectedCatalog, setSelectedCatalog] = useState('')
  const [selectedSchema, setSelectedSchema] = useState('')
  const [selectedTables, setSelectedTables] = useState(new Set())
  const [tableSearch, setTableSearch] = useState('')

  const catalogsQuery = useQuery({
    queryKey: ['catalog', 'catalogs'],
    queryFn: () => fetchJSON('/catalog/catalogs'),
  })

  const schemasQuery = useQuery({
    queryKey: ['catalog', selectedCatalog, 'schemas'],
    queryFn: () => fetchJSON(`/catalog/${selectedCatalog}/schemas`),
    enabled: Boolean(selectedCatalog),
  })

  const tablesQuery = useQuery({
    queryKey: ['catalog', selectedCatalog, selectedSchema, 'tables'],
    queryFn: () =>
      fetchJSON(`/catalog/${selectedCatalog}/${selectedSchema}/tables`),
    enabled: Boolean(selectedCatalog && selectedSchema),
  })

  const catalogs = catalogsQuery.data?.catalogs ?? []
  const schemas = schemasQuery.data?.schemas ?? []
  const tables = tablesQuery.data?.tables ?? []

  useEffect(() => {
    setSelectedSchema('')
    setSelectedTables(new Set())
    setTableSearch('')
  }, [selectedCatalog])

  useEffect(() => {
    setSelectedTables(new Set())
    setTableSearch('')
  }, [selectedSchema])

  const filteredTables = useMemo(() => {
    const q = tableSearch.trim().toLowerCase()
    if (!q) return tables
    return tables.filter(
      (t) =>
        (t.name && t.name.toLowerCase().includes(q)) ||
        (t.comment && String(t.comment).toLowerCase().includes(q)),
    )
  }, [tables, tableSearch])

  const toggleTable = (name) => {
    const next = new Set(selectedTables)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setSelectedTables(next)
    onSelect(Array.from(next), selectedCatalog, selectedSchema)
  }

  const selectAllVisible = () => {
    const next = new Set(selectedTables)
    filteredTables.forEach((t) => next.add(t.name))
    setSelectedTables(next)
    onSelect(Array.from(next), selectedCatalog, selectedSchema)
  }

  const clearSelection = () => {
    setSelectedTables(new Set())
    onSelect([], selectedCatalog, selectedSchema)
  }

  const catalogError = catalogsQuery.isError && catalogsQuery.error?.message
  const schemaError = schemasQuery.isError && schemasQuery.error?.message
  const tableError = tablesQuery.isError && tablesQuery.error?.message

  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-5 shadow-card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        Select Tables
        <HelpHint label="About: Select Tables">
          Browse your Unity Catalog to pick which tables the agent should generate metadata for. You can select multiple tables for a single session.
        </HelpHint>
      </h2>

      {catalogError && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 text-danger-800 text-sm p-3 mb-3">
          {catalogError}
        </div>
      )}
      {selectedCatalog && schemaError && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 text-danger-800 text-sm p-3 mb-3">
          {schemaError}
        </div>
      )}
      {selectedCatalog && selectedSchema && tableError && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 text-danger-800 text-sm p-3 mb-3">
          {tableError}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">Catalog</label>
          <select
            value={selectedCatalog}
            onChange={(e) => setSelectedCatalog(e.target.value)}
            className="w-full border border-border-subtle rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 bg-surface"
          >
            <option value="">Select catalog…</option>
            {catalogs.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {catalogsQuery.isLoading && (
            <p className="text-xs text-gray-400 mt-1 inline-flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" aria-hidden />
              Loading catalogs…
            </p>
          )}
          {!catalogsQuery.isLoading &&
            !catalogError &&
            catalogs.length === 0 && (
              <p className="text-xs text-amber-800 mt-2 rounded-md bg-warning-50 border border-warning-100 px-2 py-1.5">
                No catalogs returned. Check Unity Catalog permissions or workspace configuration.
              </p>
            )}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-600 mb-1">Schema</label>
          <select
            value={selectedSchema}
            onChange={(e) => setSelectedSchema(e.target.value)}
            disabled={!selectedCatalog || schemasQuery.isLoading}
            className="w-full border border-border-subtle rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 disabled:opacity-50 bg-surface"
          >
            <option value="">Select schema…</option>
            {schemas.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {selectedCatalog && schemasQuery.isLoading && (
            <p className="text-xs text-gray-400 mt-1 inline-flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" aria-hidden />
              Loading schemas…
            </p>
          )}
          {selectedCatalog &&
            !schemasQuery.isLoading &&
            !schemaError &&
            schemas.length === 0 && (
              <p className="text-xs text-gray-500 mt-2">No schemas in this catalog.</p>
            )}
        </div>
      </div>

      {selectedCatalog && selectedSchema && tablesQuery.isFetching && (
        <SkeletonRows />
      )}

      {selectedCatalog &&
        selectedSchema &&
        !tablesQuery.isFetching &&
        !tableError &&
        tables.length === 0 && (
          <p className="text-sm text-gray-500 py-4 border border-dashed border-border-subtle rounded-lg text-center px-3">
            No tables in this schema, or none visible to your account.
          </p>
        )}

      {selectedCatalog && selectedSchema && tables.length > 0 && !tablesQuery.isFetching && (
        <>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-2">
            <div className="relative flex-1">
              <Search
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
                aria-hidden
              />
              <input
                type="search"
                value={tableSearch}
                onChange={(e) => setTableSearch(e.target.value)}
                placeholder="Filter tables…"
                className="w-full border border-border-subtle rounded-lg pl-9 pr-3 py-2 text-sm focus:ring-2 focus:ring-brand-500"
                aria-label="Filter tables"
              />
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={selectAllVisible}
                className="text-xs px-3 py-2 rounded-md border border-border-subtle hover:bg-gray-50"
              >
                Select visible
              </button>
              <button
                type="button"
                onClick={clearSelection}
                className="text-xs px-3 py-2 rounded-md border border-border-subtle hover:bg-gray-50"
              >
                Clear
              </button>
            </div>
          </div>

          {filteredTables.length === 0 && (
            <p className="text-sm text-gray-500 py-3">No tables match your filter.</p>
          )}

          {filteredTables.length > 0 && (
            <div className="border border-border-subtle rounded-lg max-h-64 overflow-y-auto">
              {filteredTables.map((t) => (
                <label
                  key={t.name}
                  className="flex items-start gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0"
                >
                  <input
                    type="checkbox"
                    checked={selectedTables.has(t.name)}
                    onChange={() => toggleTable(t.name)}
                    className="mt-1 shrink-0 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                  />
                  <div className="flex-1 min-w-0 pr-1">
                    <div className="text-sm font-medium text-gray-900 break-words">{t.name}</div>
                    {t.comment && (
                      <p
                        className="text-xs text-gray-400 mt-0.5 line-clamp-2 break-words"
                        title={String(t.comment)}
                      >
                        {t.comment}
                      </p>
                    )}
                  </div>
                  {t.type && <TableTypePill type={t.type} />}
                </label>
              ))}
            </div>
          )}
        </>
      )}

      {selectedTables.size > 0 && (
        <div className="mt-3 text-sm text-brand-600 font-medium">
          {selectedTables.size} table{selectedTables.size > 1 ? 's' : ''} selected
        </div>
      )}
    </div>
  )
}
