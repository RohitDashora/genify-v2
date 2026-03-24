import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import CodeMirror from '@uiw/react-codemirror'
import { yaml as yamlLang } from '@codemirror/lang-yaml'
import { linter, lintGutter } from '@codemirror/lint'
import { githubLight } from '@uiw/codemirror-theme-github'
import jsYaml from 'js-yaml'
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  ClipboardCopy,
  FileCode,
  FileText,
  Loader2,
  RotateCcw,
  Save,
} from 'lucide-react'
import { fetchJSON } from '../../api'
import { formatCompletedLabel } from '../../utils/tableRef'
import TranscriptMarkdown from '../TranscriptMarkdown'
import HelpHint from '../HelpHint'
import MetadataBadges from './MetadataBadges'

const TITLE_ID = 'library-detail-heading'

export default function LibraryDetail() {
  const { completedId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const extensions = useMemo(() => {
    const yamlLint = (view) => {
      const doc = view.state.doc
      const text = doc.toString()
      try {
        jsYaml.load(text)
        return []
      } catch (e) {
        const mark = e.mark
        let from = 0
        let to = Math.min(1, text.length)
        if (mark && typeof mark.line === 'number') {
          try {
            const line = doc.line(mark.line + 1)
            const col = Math.min(mark.column ?? 0, Math.max(0, line.length))
            from = line.from + col
            to = Math.min(from + 1, doc.length)
          } catch {
            from = 0
            to = Math.min(1, doc.length)
          }
        }
        return [
          {
            from,
            to,
            severity: 'error',
            message: String(e.message || 'Invalid YAML').split('\n')[0],
          },
        ]
      }
    }
    return [yamlLang(), lintGutter(), linter(yamlLint)]
  }, [])

  const [mode, setMode] = useState('yaml')
  const [draftYaml, setDraftYaml] = useState(null)
  const [apiError, setApiError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [copiedYaml, setCopiedYaml] = useState(false)
  const [copiedMd, setCopiedMd] = useState(false)
  const [copyMenuOpen, setCopyMenuOpen] = useState(false)
  const copyYamlTimer = useRef(null)
  const copyMdTimer = useRef(null)
  const copyMenuRef = useRef(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['completed', completedId],
    queryFn: () => fetchJSON(`/completed/${completedId}`),
    enabled: Boolean(completedId),
  })

  const savedYaml = data?.yaml_content ?? ''
  const markdownFromServer = data?.markdown_content ?? ''
  const currentYaml = draftYaml ?? savedYaml
  const dirty = draftYaml !== null && draftYaml !== savedYaml

  useEffect(() => {
    if (!copyMenuOpen) return
    const onDoc = (e) => {
      if (copyMenuRef.current && !copyMenuRef.current.contains(e.target)) {
        setCopyMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [copyMenuOpen])

  const handleYamlChange = useCallback((value) => {
    setDraftYaml(value)
    setApiError(null)
  }, [])

  const handleSave = async () => {
    if (!dirty) return
    setSaving(true)
    setApiError(null)
    try {
      const updated = await fetchJSON(`/completed/${completedId}`, {
        method: 'PUT',
        body: JSON.stringify({ yaml_content: currentYaml }),
      })
      queryClient.setQueryData(['completed', completedId], updated)
      setDraftYaml(null)
    } catch (e) {
      setApiError(e.message || 'Save failed')
    }
    setSaving(false)
  }

  const handleRevert = () => {
    setDraftYaml(null)
    setApiError(null)
  }

  const copyToClipboard = (text, setCopied, timerRef) => {
    navigator.clipboard.writeText(text)
    if (timerRef.current) clearTimeout(timerRef.current)
    setCopied(true)
    timerRef.current = setTimeout(() => setCopied(false), 2000)
    setCopyMenuOpen(false)
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
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <nav className="shrink-0 text-xs text-gray-500 flex items-center gap-1 flex-wrap" aria-label="Breadcrumb">
        <Link to="/" className="hover:text-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded">
          Home
        </Link>
        <ChevronRight className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
        <Link to="/library" className="hover:text-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded">
          Library
        </Link>
        <ChevronRight className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
        <span className="text-gray-700 truncate max-w-[min(100%,12rem)]" title={label}>
          {label}
        </span>
      </nav>

      {/* Header */}
      <div className="shrink-0 flex items-start gap-3 flex-wrap">
        <button
          type="button"
          onClick={() => navigate('/library')}
          className="lg:hidden p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
          aria-label="Back to library"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id={TITLE_ID}
              className="text-lg font-semibold text-gray-900 truncate flex items-center gap-2"
              title={label}
            >
              {label}
              <HelpHint label="About this item">
                {mode === 'yaml'
                  ? 'YAML is the source of truth. Edit and save here; the Markdown preview is regenerated from YAML on save.'
                  : 'Read-only preview generated from YAML. Copy for documentation or paste into tools.'}
              </HelpHint>
            </h2>
            {dirty && (
              <span className="text-xs px-2 py-0.5 rounded-full border border-amber-200 bg-warning-50 text-warning-800 font-medium">
                Unsaved changes
              </span>
            )}
          </div>
          <div className="mt-1">
            <MetadataBadges templateType={data.template_type} isCombined={isCombined} />
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="shrink-0 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-border-subtle bg-gray-50 p-0.5 shrink-0">
          <button
            type="button"
            onClick={() => setMode('yaml')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors inline-flex items-center gap-1.5 ${
              mode === 'yaml'
                ? 'bg-surface shadow-sm text-gray-900'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <FileCode className="w-3.5 h-3.5 shrink-0" aria-hidden />
            YAML
          </button>
          <button
            type="button"
            onClick={() => setMode('markdown')}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors inline-flex items-center gap-1.5 ${
              mode === 'markdown'
                ? 'bg-surface shadow-sm text-gray-900'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <FileText className="w-3.5 h-3.5 shrink-0" aria-hidden />
            Markdown
          </button>
        </div>

        {mode === 'yaml' && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={!dirty || saving}
              aria-label="Save YAML. Invalid YAML is allowed; fix warnings when you can."
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
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 w-full min-[480px]:w-auto min-[480px]:ml-auto min-[480px]:justify-end">
          <div className="hidden md:flex items-center gap-2">
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

          <div className="relative md:hidden w-full min-[480px]:w-auto" ref={copyMenuRef}>
            <button
              type="button"
              onClick={() => setCopyMenuOpen((o) => !o)}
              className="w-full min-[480px]:w-auto px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 inline-flex items-center justify-center gap-1.5"
              aria-expanded={copyMenuOpen}
              aria-haspopup="true"
            >
              Copy
              <ChevronDown className="w-3.5 h-3.5 shrink-0" aria-hidden />
            </button>
            {copyMenuOpen && (
              <div
                className="absolute right-0 left-0 min-[480px]:left-auto top-full mt-1 z-20 min-w-[12rem] rounded-lg border border-border-subtle bg-surface shadow-card py-1"
                role="menu"
              >
                <button
                  type="button"
                  role="menuitem"
                  className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-2"
                  onClick={() => copyToClipboard(currentYaml, setCopiedYaml, copyYamlTimer)}
                >
                  {copiedYaml ? <Check className="w-3.5 h-3.5 text-success-700" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
                  Copy YAML
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="w-full text-left px-3 py-2 text-xs hover:bg-gray-50 flex items-center gap-2"
                  onClick={() => copyToClipboard(markdownFromServer, setCopiedMd, copyMdTimer)}
                >
                  {copiedMd ? <Check className="w-3.5 h-3.5 text-success-700" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
                  Copy Markdown
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {apiError && (
        <div className="shrink-0 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-700">
          {apiError}
        </div>
      )}

      {/* Stale markdown notice */}
      {dirty && mode === 'markdown' && (
        <div className="shrink-0 rounded-lg border border-amber-200 bg-warning-50 px-3 py-2 text-xs text-warning-800">
          Preview reflects the last saved version. Save your YAML changes to update it.
        </div>
      )}

      {/* Content pane */}
      <div
        className="rounded-xl border border-border-subtle bg-surface shadow-card overflow-hidden flex-1 min-h-0 flex flex-col"
        role="region"
        aria-labelledby={TITLE_ID}
      >
        {mode === 'yaml' ? (
          <div className="genify-cm library-cm flex min-h-0 flex-1 flex-col overflow-hidden">
            <CodeMirror
              value={currentYaml}
              theme={githubLight}
              extensions={extensions}
              onChange={handleYamlChange}
              basicSetup={{ lineNumbers: true, foldGutter: true }}
            />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
            {markdownFromServer?.trim() ? (
              <TranscriptMarkdown>{markdownFromServer}</TranscriptMarkdown>
            ) : (
              <p className="text-sm text-gray-500">
                No markdown preview yet. Save YAML to refresh — conversion is best-effort and may stay
                empty if the structure is unusual.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
