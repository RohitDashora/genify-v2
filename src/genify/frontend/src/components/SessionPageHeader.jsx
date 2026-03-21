import { ArrowLeft, ClipboardCopy, Check, WifiOff } from 'lucide-react'

const STREAM_WARNING_TOOLTIP =
  'Connection issue — the stream may reconnect automatically. If this persists, refresh the page.'

const STATUS_PILL = {
  created: 'bg-gray-100 text-gray-700',
  executing: 'bg-blue-100 text-blue-800',
  waiting_for_user: 'bg-amber-100 text-amber-900',
  complete: 'bg-success-100 text-success-700',
  failed: 'bg-danger-100 text-danger-800',
}

export default function SessionPageHeader({
  tableLabel,
  session,
  showYaml,
  onToggleYaml,
  yamlContent,
  onCopyYaml,
  copiedYaml,
  onBack,
  streamWarning = false,
}) {
  const status = session?.status

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <button
          type="button"
          onClick={onBack}
          className="md:hidden text-sm text-gray-500 hover:text-gray-700 mb-1 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden />
          Back
        </button>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold">{tableLabel || 'Session'}</h1>
          {status && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_PILL[status] || 'bg-gray-100 text-gray-700'}`}
            >
              {status.replace(/_/g, ' ')}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-gray-500 mt-1">
          <span className="capitalize">{session?.template_type?.replace('_', ' ')}</span>
          <span aria-hidden>|</span>
          <span>{session?.mode?.replace('_', ' ')}</span>
          {session?.current_step != null && (
            <>
              <span aria-hidden>|</span>
              <span>Step {session.current_step}</span>
            </>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {streamWarning && (
          <span
            className="inline-flex items-center justify-center rounded-md border border-amber-200 bg-warning-50 p-1.5 text-warning-800"
            role="status"
            title={STREAM_WARNING_TOOLTIP}
            aria-label={STREAM_WARNING_TOOLTIP}
          >
            <WifiOff className="w-4 h-4 shrink-0" aria-hidden />
          </span>
        )}
        <button
          type="button"
          onClick={onToggleYaml}
          className="text-xs px-3 py-1.5 rounded-md border border-border-subtle hover:border-gray-400 bg-surface"
        >
          {showYaml ? 'Hide YAML' : 'Show YAML'}
        </button>
        {yamlContent && (
          <button
            type="button"
            onClick={onCopyYaml}
            className="text-xs px-3 py-1.5 rounded-md border border-border-subtle hover:border-gray-400 inline-flex items-center gap-1 bg-surface"
          >
            {copiedYaml ? (
              <Check className="w-3.5 h-3.5 text-success-700" aria-hidden />
            ) : (
              <ClipboardCopy className="w-3.5 h-3.5" aria-hidden />
            )}
            {copiedYaml ? 'Copied' : 'Copy YAML'}
          </button>
        )}
      </div>
    </div>
  )
}
