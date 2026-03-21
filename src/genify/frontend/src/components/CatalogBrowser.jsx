import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Loader2 } from 'lucide-react'
import { fetchJSON } from '../api'
import HelpHint from './HelpHint'

function SkeletonRows({ n = 6 }) {
  return (
    <div className="border border-border-subtle rounded-lg overflow-hidden divide-y divide-gray-100">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3 animate-pulse">
          <div className="h-4 w-4 rounded bg-gray-200" />
          <div className="flex-1 h-4 bg-gray-200 rounded max-w-xs" />
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
                  className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0"
                >
                  <input
                    type="checkbox"
                    checked={selectedTables.has(t.name)}
                    onChange={() => toggleTable(t.name)}
                    className="rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium">{t.name}</span>
                    {t.comment && (
                      <span className="text-xs text-gray-400 ml-2 truncate">{t.comment}</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-300 uppercase shrink-0">{t.type}</span>
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
