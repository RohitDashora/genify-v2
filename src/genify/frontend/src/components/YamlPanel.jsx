import { useMemo } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { yaml as yamlLang } from '@codemirror/lang-yaml'
import { githubLight } from '@uiw/codemirror-theme-github'
import HelpHint from './HelpHint'

export default function YamlPanel({
  yamlContent,
  isEditing,
  editYaml,
  onEditYamlChange,
  isComplete,
  onStartEdit,
  onSave,
  onCancelEdit,
}) {
  const extensions = useMemo(() => [yamlLang()], [])

  return (
    <div className="bg-surface rounded-xl border border-border-subtle p-4 shadow-card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium inline-flex items-center gap-1.5">
          {isEditing ? 'Edit YAML' : 'Generated YAML'}
          <HelpHint label="About: YAML panel">
            YAML is the source of truth for this metadata. Edits here are saved to the completed record and the Markdown preview is regenerated.
          </HelpHint>
        </span>
        {isComplete && !isEditing && (
          <button
            type="button"
            onClick={onStartEdit}
            className="text-xs px-2 py-1 rounded border border-border-subtle hover:border-gray-400"
          >
            Edit
          </button>
        )}
        {isEditing && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onSave}
              className="text-xs px-2 py-1 rounded bg-brand-500 text-white"
            >
              Save
            </button>
            <button
              type="button"
              onClick={onCancelEdit}
              className="text-xs px-2 py-1 rounded border border-border-subtle"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
      {isEditing ? (
        <div className="genify-cm">
          <CodeMirror
            value={editYaml}
            height="400px"
            theme={githubLight}
            extensions={extensions}
            onChange={(v) => onEditYamlChange(v)}
            basicSetup={{ lineNumbers: true, foldGutter: true }}
          />
        </div>
      ) : (
        <div className="genify-cm">
          <CodeMirror
            value={yamlContent || 'Waiting for YAML…'}
            height="400px"
            theme={githubLight}
            extensions={extensions}
            editable={false}
            basicSetup={{ lineNumbers: true, foldGutter: true }}
          />
        </div>
      )}
    </div>
  )
}
