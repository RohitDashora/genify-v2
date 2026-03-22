import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import CodeMirror from '@uiw/react-codemirror'
import { yaml as yamlLang } from '@codemirror/lang-yaml'
import { githubLight } from '@uiw/codemirror-theme-github'
import jsYaml from 'js-yaml'
import {
  ArrowLeft,
  Check,
  ChevronRight,
  ClipboardCopy,
  Copy,
  Loader2,
  RotateCcw,
  Save,
  Star,
  Upload,
} from 'lucide-react'
import { fetchJSON } from '../../api'
import HelpHint from '../HelpHint'
import ConfirmDialog from '../ConfirmDialog'
import { templateLabel } from '../library/metadataLabels'

const TITLE_ID = 'template-detail-heading'

const EMPTY_YAML = '{}\n'

export default function TemplateDetail() {
  const { pathname } = useLocation()
  const isNew = pathname === '/templates/new'
  const { templateId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const extensions = useMemo(() => [yamlLang()], [])
  const fileInputRef = useRef(null)

  const [type, setType] = useState('table_comment')
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [yaml, setYaml] = useState(EMPTY_YAML)
  const [yamlError, setYamlError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [activating, setActivating] = useState(false)
  const [copied, setCopied] = useState(false)
  const copyTimer = useRef(null)
  const [conflictError, setConflictError] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [activateOpen, setActivateOpen] = useState(false)
  const [activateAfterNew, setActivateAfterNew] = useState(false)
  const [formError, setFormError] = useState(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['templates', templateId],
    queryFn: () => fetchJSON(`/templates/${templateId}`),
    enabled: !isNew && Boolean(templateId),
    retry: false,
  })

  useEffect(() => {
    if (!data) return
    setYaml(data.yaml_content)
    setName(data.name)
    setNotes(data.notes ?? '')
    setType(data.type)
    setYamlError(null)
    setConflictError(null)
    setFormError(null)
    setLoadError(null)
  }, [data?.id])

  useEffect(() => {
    if (!isError || !error) return
    setLoadError(error.message || 'Failed to load')
  }, [isError, error])

  const validateYaml = useCallback((value) => {
    try {
      jsYaml.load(value)
      setYamlError(null)
    } catch (e) {
      setYamlError(e.message?.split('\n')[0] || 'Invalid YAML')
    }
  }, [])

  const handleYamlChange = useCallback(
    (value) => {
      setYaml(value)
      validateYaml(value)
    },
    [validateYaml],
  )

  const savedSnapshot = data
    ? { yaml: data.yaml_content, name: data.name, notes: data.notes ?? '' }
    : null
  const dirty = isNew
    ? name.trim() !== '' || notes.trim() !== '' || yaml !== EMPTY_YAML || type !== 'table_comment'
    : savedSnapshot &&
      (yaml !== savedSnapshot.yaml || name !== savedSnapshot.name || notes !== savedSnapshot.notes)

  const invalidateAll = (id) => {
    queryClient.invalidateQueries({ queryKey: ['templates'] })
    if (id) queryClient.invalidateQueries({ queryKey: ['templates', id] })
  }

  const handleSave = async () => {
    if (yamlError) return
    if (isNew) {
      if (!name.trim()) {
        setFormError('Name is required')
        return
      }
      setFormError(null)
      setSaving(true)
      setConflictError(null)
      try {
        const created = await fetchJSON('/templates', {
          method: 'POST',
          body: JSON.stringify({
            type,
            name: name.trim(),
            yaml_content: yaml,
            notes: notes.trim() || null,
            activate: activateAfterNew,
          }),
        })
        invalidateAll(created.id)
        navigate(`/templates/${created.id}`, { replace: true })
      } catch (e) {
        setFormError(e.message || 'Create failed')
      }
      setSaving(false)
      return
    }

    if (!dirty || !templateId) return
    setSaving(true)
    setConflictError(null)
    try {
      const updated = await fetchJSON(`/templates/${templateId}`, {
        method: 'PUT',
        body: JSON.stringify({
          yaml_content: yaml,
          name: name.trim(),
          notes: notes.trim() || null,
        }),
      })
      queryClient.setQueryData(['templates', templateId], updated)
      invalidateAll(templateId)
      setYamlError(null)
    } catch (e) {
      if (e.status === 409) {
        setConflictError(e.message || 'This version is in use by active sessions.')
      } else {
        setYamlError(e.message || 'Save failed')
      }
    }
    setSaving(false)
  }

  const handleSaveAsNew = async () => {
    if (yamlError || !data) return
    setSaving(true)
    setConflictError(null)
    try {
      const created = await fetchJSON('/templates', {
        method: 'POST',
        body: JSON.stringify({
          type: data.type,
          name: name.trim() || data.name,
          yaml_content: yaml,
          notes: notes.trim() || null,
          activate: activateAfterNew,
        }),
      })
      invalidateAll(created.id)
      navigate(`/templates/${created.id}`, { replace: true })
    } catch (e) {
      setYamlError(e.message || 'Save as new version failed')
    }
    setSaving(false)
  }

  const handleClone = async () => {
    if (!templateId) return
    setSaving(true)
    setConflictError(null)
    try {
      const created = await fetchJSON(`/templates/${templateId}/clone`, {
        method: 'POST',
        body: JSON.stringify({ notes: notes.trim() || null }),
      })
      invalidateAll(created.id)
      navigate(`/templates/${created.id}`, { replace: true })
    } catch (e) {
      setYamlError(e.message || 'Clone failed')
    }
    setSaving(false)
  }

  const handleActivate = async () => {
    if (!templateId) return
    setActivating(true)
    try {
      await fetchJSON(`/templates/${templateId}/activate`, { method: 'PUT' })
      invalidateAll(templateId)
      await refetch()
      setActivateOpen(false)
    } catch (e) {
      setYamlError(e.message || 'Could not set default')
    }
    setActivating(false)
  }

  const handleRevert = () => {
    if (isNew) {
      setType('table_comment')
      setName('')
      setNotes('')
      setYaml(EMPTY_YAML)
      setYamlError(null)
      setFormError(null)
      return
    }
    if (data) {
      setYaml(data.yaml_content)
      setName(data.name)
      setNotes(data.notes ?? '')
      validateYaml(data.yaml_content)
    }
    setConflictError(null)
  }

  const copyYaml = () => {
    navigator.clipboard.writeText(yaml)
    if (copyTimer.current) clearTimeout(copyTimer.current)
    setCopied(true)
    copyTimer.current = setTimeout(() => setCopied(false), 2000)
  }

  const onPickFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const text = typeof reader.result === 'string' ? reader.result : ''
      setYaml(text)
      validateYaml(text)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  if (!isNew && templateId && isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-gray-500 text-sm">
        <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
        Loading…
      </div>
    )
  }

  if (!isNew && templateId && (isError || loadError)) {
    return (
      <div className="rounded-xl border border-danger-200 bg-danger-50 p-6 text-danger-800 space-y-3">
        <p className="font-medium text-sm">Could not load template</p>
        <p className="text-xs">{loadError || error?.message}</p>
        <Link to="/templates" className="text-sm text-brand-700 font-medium hover:underline">
          Back to templates
        </Link>
      </div>
    )
  }

  if (!isNew && !templateId) {
    return null
  }

  const showEdit = isNew || data
  const isDefault = data?.is_active

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <nav className="shrink-0 text-xs text-gray-500 flex items-center gap-1 flex-wrap" aria-label="Breadcrumb">
        <Link to="/" className="hover:text-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded">
          Home
        </Link>
        <ChevronRight className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
        <Link to="/templates" className="hover:text-gray-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded">
          Templates
        </Link>
        <ChevronRight className="w-3.5 h-3.5 shrink-0 text-gray-400" aria-hidden />
        <span className="text-gray-700 truncate max-w-[min(100%,14rem)]" title={isNew ? undefined : data?.name}>
          {isNew ? 'New version' : data?.name}
        </span>
      </nav>

      <div className="shrink-0 flex items-start gap-3 flex-wrap">
        <button
          type="button"
          onClick={() => navigate('/templates')}
          className="lg:hidden p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 rounded-lg"
          aria-label="Back to templates"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id={TITLE_ID}
              className="text-lg font-semibold text-gray-900 truncate flex items-center gap-2"
              title={!isNew ? data?.name : undefined}
            >
              {isNew ? 'New template version' : data?.name}
              <HelpHint label="About templates">
                Edit YAML for this version. <strong>Default</strong> is used for new sessions of this type.
                Saving may require a new version if an active session still pins this row.
              </HelpHint>
            </h2>
            {dirty && (
              <span className="text-xs px-2 py-0.5 rounded-full border border-amber-200 bg-warning-50 text-warning-800 font-medium">
                Unsaved changes
              </span>
            )}
          </div>
          {!isNew && data && (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border border-border-subtle bg-gray-100 text-gray-700">
                {templateLabel(data.type)}
              </span>
              <span
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border border-brand-200/80 bg-brand-50 text-brand-800"
                title={`Version ${data.version}`}
              >
                v{data.version}
              </span>
              {isDefault && (
                <span className="inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded-full border border-brand-200 bg-brand-50 text-brand-800 font-medium">
                  <Star className="w-3.5 h-3.5" aria-hidden />
                  Default
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {isNew && (
        <div className="shrink-0 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block text-xs font-medium text-gray-600">
            Type
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="mt-1 w-full border border-border-subtle rounded-lg px-3 py-2 text-sm bg-surface focus:ring-2 focus:ring-brand-500"
            >
              <option value="table_comment">Table comment</option>
              <option value="genie">Genie</option>
            </select>
          </label>
          <label className="block text-xs font-medium text-gray-600 sm:col-span-1">
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Table comment v2"
              className="mt-1 w-full border border-border-subtle rounded-lg px-3 py-2 text-sm bg-surface focus:ring-2 focus:ring-brand-500"
            />
          </label>
          <label className="block text-xs font-medium text-gray-600 sm:col-span-2">
            Notes (optional)
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="What changed in this version?"
              className="mt-1 w-full border border-border-subtle rounded-lg px-3 py-2 text-sm bg-surface focus:ring-2 focus:ring-brand-500"
            />
          </label>
        </div>
      )}

      {!isNew && data && (
        <div className="shrink-0 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block text-xs font-medium text-gray-600">
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-border-subtle rounded-lg px-3 py-2 text-sm bg-surface focus:ring-2 focus:ring-brand-500"
            />
          </label>
          <label className="block text-xs font-medium text-gray-600">
            Notes (optional)
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="mt-1 w-full border border-border-subtle rounded-lg px-3 py-2 text-sm bg-surface focus:ring-2 focus:ring-brand-500"
            />
          </label>
        </div>
      )}

      {conflictError && (
        <div className="shrink-0 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-800 space-y-2">
          <p>{conflictError}</p>
          <p className="text-danger-700/90">
            Use <strong>Save as new version</strong> or <strong>Clone to draft</strong> below. The “Set as default after save” checkbox applies to the new row.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSaveAsNew}
              disabled={saving || !!yamlError}
              className="px-2.5 py-1 rounded-lg bg-brand-500 text-white text-xs font-medium hover:bg-brand-600 disabled:opacity-40"
            >
              Save as new version
            </button>
            <button
              type="button"
              onClick={handleClone}
              disabled={saving}
              className="px-2.5 py-1 rounded-lg border border-border-subtle text-xs font-medium hover:bg-gray-50 disabled:opacity-40"
            >
              Clone to draft
            </button>
          </div>
        </div>
      )}

      <div className="shrink-0 flex flex-wrap items-center gap-2">
        <input ref={fileInputRef} type="file" accept=".yaml,.yml,.txt" className="hidden" onChange={onPickFile} />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 inline-flex items-center gap-1.5"
        >
          <Upload className="w-3.5 h-3.5" />
          Upload
        </button>
        <button
          type="button"
          onClick={copyYaml}
          className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 inline-flex items-center gap-1.5"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-success-700" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy YAML'}
        </button>
        {showEdit && (
          <>
            <button
              type="button"
              onClick={handleSave}
              disabled={
                saving ||
                !!yamlError ||
                (!isNew && !dirty) ||
                (isNew && !name.trim())
              }
              className="px-3 py-1.5 rounded-lg bg-brand-500 text-white text-xs font-medium hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              {isNew ? 'Create version' : 'Save'}
            </button>
            <button
              type="button"
              onClick={handleRevert}
              disabled={!dirty && !isNew}
              className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:border-gray-400 disabled:opacity-40 inline-flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Revert
            </button>
          </>
        )}
        {!isNew && data && (
          <>
            <button
              type="button"
              onClick={() => setActivateOpen(true)}
              disabled={activating || isDefault}
              className="px-3 py-1.5 rounded-lg border border-brand-300 text-brand-800 text-xs font-medium hover:bg-brand-50 disabled:opacity-40 inline-flex items-center gap-1.5"
            >
              {activating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Star className="w-3.5 h-3.5" />}
              Set as default
            </button>
            <button
              type="button"
              onClick={handleSaveAsNew}
              disabled={saving || !!yamlError}
              className="px-3 py-1.5 rounded-lg border border-border-subtle text-xs font-medium hover:bg-gray-50 disabled:opacity-40 inline-flex items-center gap-1.5"
            >
              <Copy className="w-3.5 h-3.5" />
              Save as new version
            </button>
          </>
        )}
      </div>

      {isNew && (
        <label className="shrink-0 flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={activateAfterNew}
            onChange={(e) => setActivateAfterNew(e.target.checked)}
          />
          Set as default after create
        </label>
      )}

      {!isNew && data && (
        <label className="shrink-0 flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={activateAfterNew}
            onChange={(e) => setActivateAfterNew(e.target.checked)}
          />
          Set as default after “Save as new version”
        </label>
      )}

      {formError && (
        <div className="shrink-0 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-700">
          {formError}
        </div>
      )}

      {yamlError && (
        <div className="shrink-0 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-700">
          {yamlError}
        </div>
      )}

      {showEdit && (
        <div
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface shadow-card"
          role="region"
          aria-labelledby={TITLE_ID}
        >
          <div className="genify-cm library-cm flex min-h-0 flex-1 flex-col overflow-hidden">
            <CodeMirror
              value={yaml}
              theme={githubLight}
              extensions={extensions}
              onChange={handleYamlChange}
              basicSetup={{ lineNumbers: true, foldGutter: true }}
            />
          </div>
        </div>
      )}

      <ConfirmDialog
        open={activateOpen}
        title="Set as default?"
        description="New sessions for this template type will use this version. Existing sessions keep the version they started with."
        confirmLabel="Set as default"
        onConfirm={handleActivate}
        onCancel={() => setActivateOpen(false)}
      />
    </div>
  )
}
