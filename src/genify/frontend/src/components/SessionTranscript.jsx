import { Loader2, Sparkles, MessageCircleWarning } from 'lucide-react'
import TranscriptMarkdown from './TranscriptMarkdown'

export default function SessionTranscript({
  messages,
  agentWorking,
  activityLine,
  question,
  isComplete,
  transcriptEndRef,
  scrollRootRef,
  onTranscriptScroll,
  showJumpLatest,
  onJumpLatest,
}) {
  return (
    <div className="relative">
      <div
        ref={scrollRootRef}
        onScroll={onTranscriptScroll}
        className="bg-surface rounded-xl border border-border-subtle p-4 min-h-[200px] max-h-[min(420px,55vh)] overflow-y-auto flex flex-col shadow-card"
        aria-label="Conversation"
      >
        <div className="text-xs font-medium text-gray-500 mb-3">Conversation</div>
        {messages.length === 0 && !agentWorking && !question && (
          <div className="text-gray-400 text-sm py-6 text-center">No messages yet.</div>
        )}
        <div className="space-y-3 flex-1">
          <div
            className={
              agentWorking && !isComplete
                ? 'space-y-3 opacity-45 pointer-events-none select-none transition-opacity'
                : 'space-y-3'
            }
            aria-busy={agentWorking && !isComplete ? true : undefined}
          >
          {messages.map((m) => {
            const isErr = m.role === 'error' || m.variant === 'error'
            const isPlan = m.role === 'system'
            const isUser = m.role === 'user'
            const isAssistant = m.role === 'assistant' && !isErr

            return (
              <div
                key={m.id}
                className={`text-sm rounded-lg px-3 py-2 ${
                  isUser
                    ? 'bg-brand-50 border border-brand-100 ml-4 sm:ml-8'
                    : isPlan
                      ? 'bg-slate-50 text-slate-700 border border-slate-200 mr-4 sm:mr-10 border-l-4 border-l-indigo-400'
                      : isErr
                        ? 'bg-danger-50 text-danger-800 border border-danger-100'
                        : 'bg-gray-50 border border-gray-100 mr-4 sm:mr-8'
                }`}
              >
                {isUser && (
                  <span className="text-[10px] uppercase text-gray-400 block mb-0.5">You</span>
                )}
                {isAssistant && (
                  <span className="text-[10px] uppercase text-brand-600 block mb-0.5 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" aria-hidden />
                    Agent
                  </span>
                )}
                {isPlan && (
                  <span className="text-[10px] uppercase text-indigo-600 block mb-0.5 font-semibold">
                    Plan
                  </span>
                )}
                {isErr && (
                  <span className="text-[10px] uppercase text-danger-700 block mb-0.5 flex items-center gap-1">
                    <MessageCircleWarning className="w-3 h-3" aria-hidden />
                    Error
                  </span>
                )}
                {isPlan || isAssistant ? (
                  <TranscriptMarkdown>{m.content}</TranscriptMarkdown>
                ) : (
                  <div className="whitespace-pre-wrap">{m.content}</div>
                )}
              </div>
            )
          })}
          </div>

          {agentWorking && !question && !isComplete && (
            <div className="border border-border-subtle rounded-lg px-3 py-2 bg-surface-muted/80">
              <div className="text-[10px] uppercase text-gray-500 font-semibold mb-1">Progress</div>
              <div className="flex items-start gap-2 text-sm text-gray-600 mr-4 sm:mr-8">
                <Loader2
                  className="w-4 h-4 shrink-0 mt-0.5 text-brand-500 animate-spin motion-reduce:animate-none"
                  aria-hidden
                />
                <div>
                  <div className="font-medium text-gray-700">Working…</div>
                  {activityLine && (
                    <div className="text-xs text-gray-500 mt-0.5">{activityLine}</div>
                  )}
                </div>
              </div>
            </div>
          )}
          <div ref={transcriptEndRef} />
        </div>
      </div>

      {showJumpLatest && (
        <button
          type="button"
          onClick={onJumpLatest}
          className="absolute bottom-3 right-3 text-xs px-3 py-1.5 rounded-full bg-brand-500 text-white shadow-md hover:bg-brand-600"
        >
          Jump to latest
        </button>
      )}
    </div>
  )
}
