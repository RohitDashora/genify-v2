import { Loader2 } from 'lucide-react'

function buildContextLine(question) {
  const section = typeof question.section === 'string' ? question.section.trim() : ''
  const field = typeof question.field === 'string' ? question.field.trim() : ''
  const parts = [section, field].filter(Boolean)
  if (parts.length === 0) return null
  return `Answering · ${parts.join(' · ')}`
}

export default function QuestionComposer({
  question,
  answer,
  onAnswerChange,
  onSend,
  sending,
  disabled,
  answerRef,
}) {
  if (!question) return null

  const suggestion = question.suggested_answer?.trim()
  const canSend = answer.trim().length > 0 && !sending && !disabled
  const contextLine = buildContextLine(question)

  const textareaAriaLabel = suggestion
    ? 'Your answer. Edit the suggested reply or type your own answer.'
    : 'Your answer. The question is in the conversation above.'

  const placeholder = suggestion
    ? 'Type your own answer, or use the suggestion above… (Ctrl+Enter to send)'
    : 'Type your answer… The question is in the conversation above. (Ctrl+Enter to send)'

  return (
    <div className="rounded-xl border border-border-subtle bg-surface p-4 shadow-card">
      <div className="mb-3">
        <div className="text-xs font-medium text-gray-500 mb-1">Your answer</div>
        {contextLine && (
          <p className="text-xs text-gray-500 truncate" title={contextLine}>
            {contextLine}
          </p>
        )}
      </div>
      {suggestion && (
        <>
          <div
            id="composer-suggested-label"
            className="text-xs font-medium text-gray-500 mb-1.5"
          >
            Suggested reply
          </div>
          <div
            role="region"
            aria-labelledby="composer-suggested-label"
            className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3"
          >
            <div className="max-h-48 overflow-y-auto text-sm whitespace-pre-wrap text-slate-800">
              {suggestion}
            </div>
          </div>
          <div
            className={`flex flex-wrap gap-2 mb-3 ${disabled ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <button
              type="button"
              disabled={disabled}
              onClick={() => onAnswerChange(suggestion)}
              className="text-xs px-3 py-1.5 rounded-full border border-brand-200 bg-brand-50 text-brand-800 hover:bg-brand-100 disabled:opacity-50"
            >
              Use suggestion
            </button>
            <button
              type="button"
              disabled={disabled || sending}
              onClick={() => onSend(suggestion)}
              className="text-xs px-3 py-1.5 rounded-full bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-50"
            >
              Send suggestion
            </button>
          </div>
        </>
      )}
      <div className="flex flex-col sm:flex-row gap-2">
        <textarea
          ref={answerRef}
          value={answer}
          onChange={(e) => onAnswerChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault()
              if (canSend) onSend()
            }
          }}
          placeholder={placeholder}
          rows={3}
          disabled={disabled}
          className="flex-1 border border-border-subtle rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 resize-y min-h-[4.5rem] disabled:bg-gray-50 disabled:text-gray-500"
          aria-label={textareaAriaLabel}
        />
        <button
          type="button"
          onClick={() => onSend()}
          disabled={!canSend}
          className="sm:self-end px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 inline-flex items-center justify-center gap-2"
        >
          {sending && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
          {sending ? 'Sending…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
