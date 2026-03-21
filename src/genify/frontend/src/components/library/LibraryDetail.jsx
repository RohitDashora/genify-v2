import { useState, useMemo, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import CodeMirror from '@uiw/react-codemirror'
import { yaml as yamlLang } from '@codemirror/lang-yaml'
import { githubLight } from '@uiw/codemirror-theme-github'
import jsYaml from 'js-yaml'
import { ArrowLeft, ClipboardCopy, Check, Loader2, RotateCcw, Save } from 'lucide-react'
import { fetchJSON } from '../../api'
import { formatCompletedLabel } from '../../utils/tableRef'
import TranscriptMarkdown from '../TranscriptMarkdown'
import HelpHint from '../HelpHint'

const TYPE_LABELS = { table_comment: 'Table comment', genie: 'Genie' }

export default function LibraryDetail() {
  const { completedId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const extensions = useMemo(() => [yamlLang()], [])

  const [mode, setMode] = useState('yaml')
  const [draftYaml, setDraftYaml] = useState(null)
  const [yamlError, setYamlError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [copiedYaml, setCopiedYaml] = useState(false)
  const [copiedMd, setCopiedMd] = useState(false)
  const copyYamlTimer = useRef(null)
  const copyMdTimer = useRef(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['completed', completedId],
    queryFn: () => fetchJSON(`/completed/${completedId}`),
    enabled: Boolean(completedId),
  })

  const savedYaml = data?.yaml_content ?? ''
  const markdownFromServer = data?.markdown_content ?? ''
  const currentYaml = draftYaml ?? savedYaml
  const dirty = draftYaml !== null && draftYaml !== savedYaml

  const handleYamlChange = useCallback((value) => {
    setDraftYaml(value)
    try {
      jsYaml.load(value)
      setYamlError(null)
    } catch (e) {
      setYamlError(e.message?.split('\n')[0] || 'Invalid YAML')
    }
  }, [])

  const handleSave = async () => {
    if (!dirty || yamlError) return
    setSaving(true)
    try {
      const updated = await fetchJSON(`/completed/${completedId}`, {
        method: 'PUT',
        body: JSON.stringify({ yaml_content: currentYaml }),
      })
      queryClient.setQueryData(['completed', completedId], updated)
      setDraftYaml(null)
      setYamlError(null)
    } catch (e) {
      setYamlError(`Save failed: ${e.message}`)
    }
    setSaving(false)
  }

  const handleRevert = () => {
    setDraftYaml(null)
    setYamlError(null)
  }

  const copyToClipboard = (text, setCopied, timerRef) => {
    navigator.clipboard.writeText(text)
    if (timerRef.current) clearTimeout(timerRef.current)
    setCopied(true)
    timerRef.current = setTimeout(() => setCopied(false), 2000)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-gray-500 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
        Loading...
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-danger-200 bg-danger-50 p-6 text-danger-800">
        <p className="font-medium text-sm">Could not load item</p>
        <p className="text-xs mt-1">{error?.message}</p>
      </div>
    )
  }

  if (!data) return null

  const { label, isCombined } = formatCompletedLabel(data.table_fqn, data.table_ref)

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-start gap-3 flex-wrap">
        <button
          type="button"
          onClick={() => navigate('/library')}
          className="lg:hidden p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 shrink-0"
          aria-label="Back to library"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-gray-900 truncate flex items-center gap-2" title={label}>
            {label}
            <HelpHint label="About this item">
              {mode === 'yaml'
                ? 'YAML is the source of truth. Edit and save here; the Markdown preview is regenerated from YAML on save.'
                : 'Read-only preview generated from YAML. Copy for documentation or paste into tools.'}
            </HelpHint>
          </h2>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600">
              {TYPE_LABELS[data.template_type] || data.template_type}
            </span>
            {isCombined && (
              <span className="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium bg-blue-50 text-blue-700">
                Combined
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Toggle + actions */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="inline-flex rounded-lg border border-border-subtle bg-gray-50 p-0.5">
          {['yaml', 'markdown'].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                mode === m
                  ? 'bg-surface shadow-sm text-gray-900'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {m === 'yaml' ? 'YAML' : 'Markdown'}
            </button>
          ))}
        </div>

        {mode === 'yaml' && (
          <>
            <button
              type="button"
              onClick={handleSave}
              disabled={!dirty || yamlError || saving}
              className="px-3 py-1.5 rounded-lg bg-brand-500 text-white text-xs font-medium hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              Save
            </button>
            <button
              type="button"
              onClick={handleRevert}
              disabled={!dirty}
              className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Revert
            </button>
          </>
        )}

        <div className="flex items-center gap-2 ml-auto">
          <button
            type="button"
            onClick={() => copyToClipboard(currentYaml, setCopiedYaml, copyYamlTimer)}
            className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 inline-flex items-center gap-1.5"
          >
            {copiedYaml ? <Check className="w-3.5 h-3.5 text-success-700" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
            {copiedYaml ? 'Copied' : 'Copy YAML'}
          </button>
          <button
            type="button"
            onClick={() => copyToClipboard(markdownFromServer, setCopiedMd, copyMdTimer)}
            className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 inline-flex items-center gap-1.5"
          >
            {copiedMd ? <Check className="w-3.5 h-3.5 text-success-700" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
            {copiedMd ? 'Copied' : 'Copy Markdown'}
          </button>
        </div>
      </div>

      {/* Validation error */}
      {yamlError && mode === 'yaml' && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-700">
          {yamlError}
        </div>
      )}

      {/* Stale markdown notice */}
      {dirty && mode === 'markdown' && (
        <div className="rounded-lg border border-amber-200 bg-warning-50 px-3 py-2 text-xs text-warning-800">
          Preview reflects the last saved version. Save your YAML changes to update it.
        </div>
      )}

      {/* Content pane */}
      <div className="rounded-xl border border-border-subtle bg-surface shadow-card overflow-hidden">
        {mode === 'yaml' ? (
          <div className="genify-cm library-cm">
            <CodeMirror
              value={currentYaml}
              theme={githubLight}
              extensions={extensions}
              onChange={handleYamlChange}
              basicSetup={{ lineNumbers: true, foldGutter: true }}
            />
          </div>
        ) : (
          <div className="p-4 sm:p-6 overflow-auto max-h-[70vh]">
            {markdownFromServer ? (
              <TranscriptMarkdown>{markdownFromServer}</TranscriptMarkdown>
            ) : (
              <p className="text-sm text-gray-400">No markdown preview available.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
