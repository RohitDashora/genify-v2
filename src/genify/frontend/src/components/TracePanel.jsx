import { useEffect, useRef, useState } from 'react'
import {
  Brain,
  Wrench,
  Sparkles,
  ListOrdered,
  Clock,
  Settings2,
  ChevronDown,
  ChevronRight,
  HelpCircle,
} from 'lucide-react'

const MAX_LINES = 500

const CATEGORY_CLASS = {
  thinking: 'text-slate-600',
  tool: 'text-emerald-700',
  llm: 'text-violet-700',
  plan: 'text-blue-700',
  wait: 'text-amber-700',
  system: 'text-slate-500',
}

const CATEGORY_ICON = {
  thinking: Brain,
  tool: Wrench,
  llm: Sparkles,
  plan: ListOrdered,
  wait: Clock,
  system: Settings2,
}

export default function TracePanel({ lines, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (open) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [lines, open])

  const copyAll = () => {
    const text = lines
      .map((l) => {
        const parts = [l.message]
        if (l.tool) parts.push(`tool=${l.tool}`)
        if (l.table_fqn) parts.push(`table=${l.table_fqn}`)
        if (l.detail) parts.push(l.detail)
        return parts.join(' | ')
      })
      .join('\n')
    navigator.clipboard.writeText(text)
  }

  const capped = lines.length > MAX_LINES ? lines.slice(-MAX_LINES) : lines

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-950 text-slate-100 overflow-hidden shadow-card">
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700 bg-slate-900">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="text-xs font-medium text-slate-300 hover:text-white inline-flex items-center gap-1"
          aria-expanded={open}
        >
          {open ? (
            <ChevronDown className="w-3.5 h-3.5" aria-hidden />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" aria-hidden />
          )}
          Activity trace
        </button>
        <span className="relative inline-flex items-center group ml-1">
          <button
            type="button"
            className="p-0.5 rounded text-slate-500 hover:text-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500"
            aria-label="About: Activity trace"
          >
            <HelpCircle className="w-3 h-3" />
          </button>
          <span
            role="tooltip"
            className="pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50 w-max max-w-xs px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 shadow-card text-xs text-slate-200 leading-relaxed opacity-0 invisible transition-opacity duration-150 group-hover:opacity-100 group-hover:visible group-focus-within:opacity-100 group-focus-within:visible"
          >
            Verbose diagnostics: MCP tool calls, LLM phases, and timing. Useful for debugging. Copy for support.
          </span>
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={copyAll}
            disabled={lines.length === 0}
            className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40"
          >
            Copy
          </button>
        </div>
      </div>
      {open && (
        <div className="font-mono text-[11px] leading-relaxed max-h-[280px] overflow-y-auto px-3 py-2">
          {capped.length === 0 && (
            <div className="text-slate-500 py-4 text-center">Waiting for agent activity…</div>
          )}
          {capped.map((line, i) => {
            const Icon = CATEGORY_ICON[line.category] || Settings2
            return (
              <div
                key={`${line.ts}-${i}`}
                className={`py-1 border-b border-slate-800/80 last:border-0 hover:bg-slate-900/50 rounded-sm -mx-1 px-1 ${CATEGORY_CLASS[line.category] || 'text-slate-400'}`}
              >
                <div className="flex items-start gap-1.5">
                  <Icon className="w-3.5 h-3.5 shrink-0 mt-0.5 opacity-80" aria-hidden />
                  <div className="min-w-0 flex-1">
                    {line.phase && (
                      <span className="inline-block text-[10px] uppercase tracking-wide text-slate-500 bg-slate-800/80 px-1 rounded mr-1">
                        {line.phase}
                      </span>
                    )}
                    <span>{line.message}</span>
                    {line.tool && (
                      <span className="ml-1 text-emerald-400/90">({line.tool})</span>
                    )}
                    {line.table_fqn && (
                      <span className="ml-1 text-sky-400/80">@{line.table_fqn}</span>
                    )}
                    {line.detail && (
                      <div className="mt-0.5 pl-1 text-slate-400 whitespace-pre-wrap break-all">
                        {line.detail}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
