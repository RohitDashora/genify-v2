import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { formatRelative } from 'date-fns'
import { fetchJSON } from '../../api'
import { formatCompletedLabel } from '../../utils/tableRef'
import HelpHint from '../HelpHint'

const TYPE_LABELS = { table_comment: 'Table comment', genie: 'Genie' }

export default function LibraryList({ selectedId }) {
  const navigate = useNavigate()

  const { data: items, isLoading, isError, error } = useQuery({
    queryKey: ['completed'],
    queryFn: () => fetchJSON('/completed'),
  })

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold text-gray-900">Saved metadata</h2>
        <HelpHint label="About: Saved metadata">
          Completed YAML outputs from your sessions. Click a card to view, edit, or copy.
        </HelpHint>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 py-8 justify-center text-gray-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
          Loading...
        </div>
      )}

      {isError && (
        <p className="text-sm text-danger-700">Failed to load: {error?.message}</p>
      )}

      {items?.length === 0 && (
        <div className="rounded-xl border border-border-subtle bg-surface p-6 text-center text-sm text-gray-500">
          <p>No saved metadata yet.</p>
          <a href="/" className="text-brand-500 hover:underline mt-1 inline-block">
            Start a session
          </a>
        </div>
      )}

      <div className="space-y-2">
        {items?.map((item) => {
          const { label, isCombined } = formatCompletedLabel(item.table_fqn, item.table_ref)
          const isSelected = item.id === selectedId
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => navigate(`/library/${item.id}`)}
              className={`w-full text-left rounded-xl border p-3 transition-colors ${
                isSelected
                  ? 'border-brand-500 bg-brand-50 shadow-card'
                  : 'border-border-subtle bg-surface hover:border-gray-300 shadow-card'
              }`}
            >
              <p className="text-sm font-medium text-gray-900 truncate" title={label}>
                {label}
              </p>
              <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                <span className="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600">
                  {TYPE_LABELS[item.template_type] || item.template_type}
                </span>
                {isCombined && (
                  <span className="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium bg-blue-50 text-blue-700">
                    Combined
                  </span>
                )}
                <span className="text-[11px] text-gray-400">
                  {formatRelative(new Date(item.updated_at), new Date())}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
