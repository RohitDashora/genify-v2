import { Loader2 } from 'lucide-react'

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

  return (
    <div className="rounded-xl border border-border-subtle bg-surface p-4 shadow-card">
      <div className="text-sm font-medium text-gray-800 mb-1">Your answer</div>
      <p id="composer-question-text" className="text-sm text-gray-700 mb-3">
        {question.question}
      </p>
      {suggestion && (
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
          placeholder="Type your answer… (Ctrl+Enter to send)"
          rows={3}
          disabled={disabled}
          className="flex-1 border border-border-subtle rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 resize-y min-h-[4.5rem] disabled:bg-gray-50 disabled:text-gray-500"
          aria-labelledby="composer-question-text"
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
