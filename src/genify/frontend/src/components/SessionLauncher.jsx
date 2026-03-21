import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, X } from 'lucide-react'
import { fetchJSON } from '../api'
import HelpHint from './HelpHint'

export default function SessionLauncher({ selectedTables, catalog, schema }) {
  const [templateType, setTemplateType] = useState('table_comment')
  const [mode, setMode] = useState('hands_off')
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const isGenie = templateType === 'genie'
  const canStart =
    selectedTables.length > 0 &&
    (isGenie ? selectedTables.length >= 1 : selectedTables.length === 1)

  const startHint = (() => {
    if (canStart) return null
    if (!selectedTables.length) return 'Select at least one table from the catalog above.'
    if (!isGenie && selectedTables.length !== 1) {
      return 'Table Comment requires exactly one table. Switch to Genie Space for multiple tables.'
    }
    return null
  })()

  const handleStart = async () => {
    setStarting(true)
    setError('')
    try {
      const tableRef = isGenie
        ? {
            catalog,
            schema,
            tables: selectedTables.map((t) => ({ catalog, schema, table: t })),
          }
        : { catalog, schema, table: selectedTables[0] }

      const body = {
        template_type: templateType,
        mode: isGenie ? 'interactive' : mode,
        table_ref: tableRef,
        output_format: 'yaml',
      }

      const result = await fetchJSON('/sessions', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      navigate(`/session/${result.session_id}`)
    } catch (e) {
      setError(e.message)
      setStarting(false)
    }
  }

  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-5 shadow-card">
      <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
        Start Session
        <HelpHint label="About: Start Session">
          Choose a template type and mode, then launch the agent. Interactive mode asks clarifying questions; hands-off generates everything automatically.
        </HelpHint>
      </h2>

      {error && (
        <div className="rounded-lg border border-amber-200 bg-warning-50 text-warning-800 text-sm p-3 mb-3 flex items-start justify-between gap-2">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError('')}
            className="shrink-0 p-0.5 rounded text-amber-800 hover:bg-amber-100"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="flex gap-3 mb-4">
        <button
          type="button"
          onClick={() => setTemplateType('table_comment')}
          className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium border transition-colors ${
            !isGenie
              ? 'bg-brand-500 text-white border-brand-500'
              : 'bg-surface text-gray-600 border-border-subtle hover:border-gray-400'
          }`}
        >
          Table Comment
        </button>
        <button
          type="button"
          onClick={() => setTemplateType('genie')}
          className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium border transition-colors ${
            isGenie
              ? 'bg-brand-500 text-white border-brand-500'
              : 'bg-surface text-gray-600 border-border-subtle hover:border-gray-400'
          }`}
        >
          Genie Space
        </button>
      </div>

      {!isGenie && (
        <div className="mb-4">
          <span className="block text-sm font-medium text-gray-600 mb-2">Mode</span>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="mode"
                value="hands_off"
                checked={mode === 'hands_off'}
                onChange={(e) => setMode(e.target.value)}
                className="text-brand-500 focus:ring-brand-500"
              />
              <span className="text-sm">Hands-off</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="mode"
                value="interactive"
                checked={mode === 'interactive'}
                onChange={(e) => setMode(e.target.value)}
                className="text-brand-500 focus:ring-brand-500"
              />
              <span className="text-sm">Interactive</span>
            </label>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            {mode === 'hands_off'
              ? 'Agent fills everything automatically. Marks unknowns as NEEDS_CLARIFICATION.'
              : 'Agent asks you when uncertain. Chat-like experience.'}
          </p>
        </div>
      )}

      {isGenie && (
        <p className="text-xs text-gray-400 mb-4">
          Genie mode is always interactive. Select one or more tables.
        </p>
      )}

      {startHint && (
        <p className="text-xs text-gray-500 mb-3 rounded-md bg-gray-50 border border-border-subtle px-3 py-2">
          {startHint}
        </p>
      )}

      <button
        type="button"
        onClick={handleStart}
        disabled={!canStart || starting}
        className="w-full py-2.5 rounded-lg text-sm font-medium bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center justify-center gap-2"
      >
        {starting && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
        {starting ? 'Starting…' : canStart ? 'Start Session' : 'Select table(s) to start'}
      </button>
    </div>
  )
}
