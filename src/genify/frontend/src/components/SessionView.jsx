import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardCopy, Download, Loader2, BookMarked } from 'lucide-react'
import { fetchJSON, connectSSE } from '../api'
import TracePanel from './TracePanel'
import SessionPageHeader from './SessionPageHeader'
import SessionTranscript from './SessionTranscript'
import QuestionComposer from './QuestionComposer'
import YamlPanel from './YamlPanel'

const STRATEGY_LABELS = {
  auto_fill: 'Fill from data',
  partial_fill_then_ask: 'Draft, then ask you',
  ask_user: 'Ask you',
  skip: 'Skip (optional)',
}

const TRACE_CAP = 500

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function hydrateFromConversation(conversation) {
  if (!Array.isArray(conversation)) return []
  return conversation.map((m, idx) => ({
    id: `h-${idx}-${m.role}`,
    role: m.role === 'user' ? 'user' : 'assistant',
    content: typeof m.content === 'string' ? m.content : '',
  }))
}

/** Stable id for an interactive pause (replay / suggestion updates must not clear the composer draft). */
function questionPauseKey(d) {
  if (!d || typeof d !== 'object') return ''
  const s = String(d.section ?? '').trim()
  const f = String(d.field ?? '').trim()
  const q = String(d.question ?? '').trim()
  return `${s}\0${f}\0${q}`
}

export default function SessionView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const answerRef = useRef(null)

  const [messages, setMessages] = useState([])
  const [traceLines, setTraceLines] = useState([])
  const [yamlContent, setYamlContent] = useState('')
  const [question, setQuestion] = useState(null)
  const [answer, setAnswer] = useState('')
  const [isComplete, setIsComplete] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editYaml, setEditYaml] = useState('')
  const [showYaml, setShowYaml] = useState(false)
  const [sending, setSending] = useState(false)
  const [agentWorking, setAgentWorking] = useState(true)
  const [activityLine, setActivityLine] = useState('Connecting…')
  const [answerBanner, setAnswerBanner] = useState(null)
  const [streamEpoch, setStreamEpoch] = useState(0)
  const [streamWarning, setStreamWarning] = useState(false)
  const [copiedYaml, setCopiedYaml] = useState(false)
  const [showJumpLatest, setShowJumpLatest] = useState(false)
  const [ariaQuestion, setAriaQuestion] = useState('')

  const esRef = useRef(null)
  const includePlanRef = useRef(true)
  /** Suppress stream warning while waiting on a question (SSE often ends normally after `question`). */
  const questionRef = useRef(null)
  /** Last handled SSE `question` pause; same key = replay — merge payload only, keep draft. */
  const lastQuestionPauseKeyRef = useRef('')
  const sessionPlanFromStreamRef = useRef(false)
  const transcriptEndRef = useRef(null)
  const scrollRootRef = useRef(null)
  const userAtBottomRef = useRef(true)
  const streamErrTimer = useRef(null)
  const terminalFailHandledRef = useRef(false)
  const completionBannerAddedRef = useRef(false)
  const copyTimerRef = useRef(null)
  const completedIdRef = useRef(null)

  const {
    data: session,
    isLoading: sessionLoading,
    isSuccess: sessionSuccess,
    isError: sessionError,
    error: sessionErr,
    refetch: refetchSession,
  } = useQuery({
    queryKey: ['session', id],
    queryFn: () => fetchJSON(`/sessions/${id}`),
    enabled: Boolean(id),
  })

  const tableLabel = session?.table_ref
    ? session.table_ref.table
      ? `${session.table_ref.catalog}.${session.table_ref.schema}.${session.table_ref.table}`
      : `${session.table_ref.catalog}.${session.table_ref.schema}.*`
    : ''

  useEffect(() => {
    const prev = document.title
    if (tableLabel) document.title = `${tableLabel} · Genify`
    return () => {
      document.title = prev
    }
  }, [tableLabel])

  const appendTrace = useCallback((payload) => {
    setTraceLines((prev) => {
      const row = { ...payload, ts: Date.now() }
      const next = [...prev, row]
      return next.length > TRACE_CAP ? next.slice(-TRACE_CAP) : next
    })
  }, [])

  const addMessage = useCallback((role, content, variant) => {
    if (!content && role !== 'system') return
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, content, variant },
    ])
  }, [])

  const checkAtBottom = useCallback(() => {
    const el = scrollRootRef.current
    if (!el) return true
    const threshold = 72
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  }, [])

  const handleTranscriptScroll = useCallback(() => {
    const at = checkAtBottom()
    userAtBottomRef.current = at
    if (at) setShowJumpLatest(false)
  }, [checkAtBottom])

  const jumpToLatest = useCallback(() => {
    userAtBottomRef.current = true
    setShowJumpLatest(false)
    transcriptEndRef.current?.scrollIntoView({
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    })
  }, [])

  useEffect(() => {
    setMessages([])
    setTraceLines([])
    setYamlContent('')
    setQuestion(null)
    setAnswer('')
    setIsComplete(false)
    setIsEditing(false)
    setEditYaml('')
    setShowYaml(false)
    setAnswerBanner(null)
    setAgentWorking(true)
    setActivityLine('Connecting…')
    includePlanRef.current = true
    sessionPlanFromStreamRef.current = false
    setStreamEpoch(0)
    setStreamWarning(false)
    terminalFailHandledRef.current = false
    completionBannerAddedRef.current = false
    userAtBottomRef.current = true
    setShowJumpLatest(false)
    lastQuestionPauseKeyRef.current = ''
    esRef.current?.close()
  }, [id])

  useEffect(() => {
    if (!session?.conversation?.length || messages.length > 0) return
    setMessages(hydrateFromConversation(session.conversation))
  }, [session, messages.length])

  // Refresh / deep link: restore composer from persisted pending_question (no SSE yet).
  useEffect(() => {
    if (!session || isComplete) return
    if (session.status !== 'waiting_for_user' || question) return
    const pq = session.pending_question
    if (!pq || typeof pq !== 'object') return
    setQuestion({
      question: pq.question || '',
      suggested_answer: pq.suggested_answer || '',
      section: pq.section,
      field: pq.field,
    })
    lastQuestionPauseKeyRef.current = questionPauseKey({
      section: pq.section,
      field: pq.field,
      question: pq.question || '',
    })
    setAgentWorking(false)
    setActivityLine('')
    if (session.generated_yaml) {
      setYamlContent((y) => y || session.generated_yaml || '')
    }
  }, [session, question, isComplete])

  useEffect(() => {
    if (!session) return
    if (session.status === 'complete') {
      setIsComplete(true)
      setAgentWorking(false)
      setActivityLine('')
      setYamlContent((y) => y || session.generated_yaml || '')
    }
    if (session.status === 'failed' && !terminalFailHandledRef.current) {
      terminalFailHandledRef.current = true
      setAgentWorking(false)
      setActivityLine('')
      addMessage('error', session.error_message || 'Session failed', 'error')
    }
  }, [session, addMessage])

  useEffect(() => {
    if (userAtBottomRef.current) {
      transcriptEndRef.current?.scrollIntoView({
        behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      })
      setShowJumpLatest(false)
    } else {
      setShowJumpLatest(true)
    }
  }, [messages, activityLine, agentWorking, question, isComplete])

  useEffect(() => {
    if (question?.question) {
      setAriaQuestion(`New question: ${question.question}`)
    } else {
      setAriaQuestion('')
    }
  }, [question])

  const questionFocusKey = question ? questionPauseKey(question) : ''
  useEffect(() => {
    if (!questionFocusKey || !answerRef.current) return
    const t = setTimeout(() => answerRef.current?.focus(), 100)
    return () => clearTimeout(t)
  }, [questionFocusKey])

  useEffect(() => {
    questionRef.current = question
  }, [question])

  useEffect(() => {
    if (!answerBanner) return
    const fn = (e) => {
      if (e.key === 'Escape') setAnswerBanner(null)
    }
    window.addEventListener('keydown', fn)
    return () => window.removeEventListener('keydown', fn)
  }, [answerBanner])

  const buildHandlers = useCallback(
    (includePlanDetail) => ({
      onOpen: () => {
        setAgentWorking(true)
        setActivityLine((line) => (line === 'Connecting…' ? 'Working…' : line))
      },
      onStatus: (d) => {
        if (d?.message) setActivityLine(d.message)
      },
      onThinking: (d) => {
        if (d?.message) setActivityLine(d.message)
      },
      onTrace: (d) =>
        appendTrace({
          category: d.category || 'system',
          message: d.message || '',
          tool: d.tool,
          detail: d.detail,
          phase: d.phase,
          table_fqn: d.table_fqn,
        }),
      onPlan: (d) => {
        if (!includePlanDetail) return
        if (sessionPlanFromStreamRef.current) return
        sessionPlanFromStreamRef.current = true
        const steps = d.steps || []
        const lines = steps.map(
          (s) =>
            `• ${s.section_key}: ${STRATEGY_LABELS[s.strategy] || s.strategy}`,
        )
        const head = `Plan ready — ${d.total_sections} sections (${d.estimated_time || 'in progress'})`
        addMessage('system', [head, ...lines].join('\n'))
      },
      onYamlChunk: (d) => {
        setYamlContent((prev) => {
          if (d.is_complete) return prev + '\n' + d.content
          return prev + d.content
        })
      },
      onSectionComplete: (d) => {
        setActivityLine(`${d.section} done (${d.step}/${d.total})`)
      },
      onQuestion: (d) => {
        if (streamErrTimer.current) clearTimeout(streamErrTimer.current)
        setStreamWarning(false)
        questionRef.current = d
        const key = questionPauseKey(d)
        const samePause = Boolean(key) && key === lastQuestionPauseKeyRef.current
        if (samePause) {
          setQuestion(d)
          return
        }
        lastQuestionPauseKeyRef.current = key
        setQuestion(d)
        setAnswer('')
        setAgentWorking(false)
        setActivityLine('')
        const text = d.question
        setMessages((prev) => {
          if (prev.some((m) => m.role === 'assistant' && m.content === text)) return prev
          return [...prev, { id: crypto.randomUUID(), role: 'assistant', content: text }]
        })
      },
      onComplete: (d) => {
        setYamlContent((prev) => d.yaml || prev)
        setIsComplete(true)
        setAgentWorking(false)
        setActivityLine('')
        if (d.completed_id) completedIdRef.current = d.completed_id
        if (!completionBannerAddedRef.current) {
          completionBannerAddedRef.current = true
          addMessage(
            'assistant',
            'Your metadata is ready. Use **Show YAML** to review or download.',
            'success',
          )
        }
        queryClient.invalidateQueries({ queryKey: ['session', id] })
        queryClient.invalidateQueries({ queryKey: ['sessions'] })
        queryClient.invalidateQueries({ queryKey: ['completed'] })
      },
      onError: (d) => {
        setAgentWorking(false)
        setActivityLine('')
        addMessage('error', d.message || 'Something went wrong', 'error')
      },
      onDisconnect: () => {},
    }),
    [addMessage, appendTrace, queryClient, id],
  )

  useEffect(() => {
    if (!id || sessionLoading || sessionError || !sessionSuccess) return

    // Close any prior stream before opening a new one (remount, streamEpoch bump, Strict Mode).
    try {
      esRef.current?.close()
    } catch {
      /* ignore */
    }
    esRef.current = null

    const handlers = buildHandlers(includePlanRef.current)
    const es = connectSSE(id, {
      ...handlers,
      onOpen: () => {
        if (streamErrTimer.current) clearTimeout(streamErrTimer.current)
        setStreamWarning(false)
        if (!questionRef.current) handlers.onOpen()
      },
      onQuestion: (d) => {
        handlers.onQuestion(d)
        try {
          es.close()
        } catch {
          /* ignore */
        }
        if (esRef.current === es) esRef.current = null
      },
      onStreamError: () => {
        if (streamErrTimer.current) clearTimeout(streamErrTimer.current)
        // After `question`, the server often ends the SSE response; that is not a user-visible outage.
        if (questionRef.current) return
        streamErrTimer.current = setTimeout(() => setStreamWarning(true), 1200)
      },
      onComplete: (d) => {
        handlers.onComplete(d)
        es.close()
      },
      onError: (d) => {
        handlers.onError(d)
        es.close()
      },
    })

    esRef.current = es
    return () => {
      if (streamErrTimer.current) clearTimeout(streamErrTimer.current)
      es.close()
      if (esRef.current === es) esRef.current = null
    }
  }, [id, sessionSuccess, sessionLoading, sessionError, streamEpoch, buildHandlers])

  const handleSendAnswer = async (overrideText) => {
    const raw = overrideText != null ? String(overrideText).trim() : answer.trim()
    if (!raw) return
    setSending(true)
    setAnswerBanner(null)
    try {
      await fetchJSON(`/sessions/${id}/answer`, {
        method: 'POST',
        body: JSON.stringify({ answer: raw }),
      })
      addMessage('user', raw)
      setQuestion(null)
      lastQuestionPauseKeyRef.current = ''
      setAnswer('')
      appendTrace({
        category: 'system',
        message: 'Answer submitted — resuming',
        phase: 'system',
      })
      queryClient.invalidateQueries({ queryKey: ['session', id] })
      includePlanRef.current = false
      setAgentWorking(true)
      setActivityLine('Working…')
      esRef.current?.close()
      setStreamEpoch((e) => e + 1)
    } catch (e) {
      const code = e.code
      const msg = e.message || ''
      if (code === 'not_waiting_for_user' || msg.includes('not waiting for answer')) {
        setAnswerBanner(
          'The agent is not ready for an answer yet. Wait until you see a question above, then try again.',
        )
      } else if (code === 'answer_already_queued') {
        setAnswerBanner(
          'Your previous answer is still queued. Reconnect or wait for the agent to process it before sending another.',
        )
      } else {
        setAnswerBanner(msg)
      }
    }
    setSending(false)
  }

  const handleSaveEdit = async () => {
    try {
      let targetId = completedIdRef.current
      if (!targetId) {
        const rows = await fetchJSON(`/sessions/${id}/completed`)
        if (rows?.length) targetId = rows[0].id
      }
      if (!targetId) {
        addMessage('error', 'No completed metadata found for this session.', 'error')
        return
      }
      await fetchJSON(`/completed/${targetId}`, {
        method: 'PUT',
        body: JSON.stringify({ yaml_content: editYaml }),
      })
      setYamlContent(editYaml)
      setIsEditing(false)
      addMessage('system', 'Saved changes to completed metadata.')
      queryClient.invalidateQueries({ queryKey: ['completed'] })
    } catch (e) {
      addMessage('error', `Save failed: ${e.message}`, 'error')
    }
  }

  const copyYaml = () => {
    navigator.clipboard.writeText(yamlContent)
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    setCopiedYaml(true)
    copyTimerRef.current = setTimeout(() => setCopiedYaml(false), 2000)
  }

  if (!id) return null

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin" aria-hidden />
        <span>Loading session…</span>
      </div>
    )
  }

  if (sessionError) {
    return (
      <div className="rounded-xl border border-danger-200 bg-danger-50 p-6 text-danger-800">
        <p className="font-medium">Could not load session</p>
        <p className="text-sm mt-1">{sessionErr?.message || 'Unknown error'}</p>
        <button
          type="button"
          onClick={() => refetchSession()}
          className="mt-4 text-sm px-3 py-1.5 rounded-lg border border-danger-300 hover:bg-danger-100"
        >
          Retry
        </button>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="mt-4 ml-2 text-sm px-3 py-1.5 rounded-lg border border-border-subtle"
        >
          Back home
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="sr-only" aria-live="polite">
        {ariaQuestion}
      </div>

      <SessionPageHeader
        tableLabel={tableLabel}
        session={session}
        showYaml={showYaml}
        onToggleYaml={() => setShowYaml(!showYaml)}
        yamlContent={yamlContent}
        onCopyYaml={copyYaml}
        copiedYaml={copiedYaml}
        onBack={() => navigate('/')}
        streamWarning={streamWarning && !isComplete}
      />

      <div
        className={`grid gap-4 ${showYaml ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'}`}
      >
        <div className="space-y-3 min-h-0 order-2 lg:order-1">
          <SessionTranscript
            messages={messages}
            agentWorking={agentWorking}
            activityLine={activityLine}
            question={question}
            isComplete={isComplete}
            transcriptEndRef={transcriptEndRef}
            scrollRootRef={scrollRootRef}
            onTranscriptScroll={handleTranscriptScroll}
            showJumpLatest={showJumpLatest}
            onJumpLatest={jumpToLatest}
          />
          <TracePanel lines={traceLines} defaultOpen={false} />
        </div>

        {showYaml && (
          <div className="order-1 lg:order-2">
            <YamlPanel
              yamlContent={yamlContent}
              isEditing={isEditing}
              editYaml={editYaml}
              onEditYamlChange={setEditYaml}
              isComplete={isComplete}
              onStartEdit={() => {
                setIsEditing(true)
                setEditYaml(yamlContent)
              }}
              onSave={handleSaveEdit}
              onCancelEdit={() => setIsEditing(false)}
            />
          </div>
        )}
      </div>

      {answerBanner && (
        <div
          className="rounded-lg border border-amber-200 bg-warning-50 px-4 py-3 text-sm text-warning-800 flex items-start justify-between gap-3"
          role="status"
        >
          <span>{answerBanner}</span>
          <button
            type="button"
            onClick={() => setAnswerBanner(null)}
            className="text-amber-800 hover:text-amber-950 shrink-0 text-xs underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {question && !isComplete && (
        <QuestionComposer
          question={question}
          answer={answer}
          onAnswerChange={setAnswer}
          onSend={handleSendAnswer}
          sending={sending}
          disabled={Boolean(answerBanner) || agentWorking}
          answerRef={answerRef}
        />
      )}

      {isComplete && (
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={copyYaml}
            className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 inline-flex items-center gap-2"
          >
            <ClipboardCopy className="w-4 h-4" aria-hidden />
            {copiedYaml ? 'Copied' : 'Copy YAML'}
          </button>
          <button
            type="button"
            onClick={() => {
              const blob = new Blob([yamlContent], { type: 'text/yaml' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `${tableLabel.replace(/\./g, '_')}.yaml`
              a.click()
              URL.revokeObjectURL(url)
            }}
            className="px-4 py-2 rounded-lg border border-border-subtle text-sm font-medium hover:border-gray-400 inline-flex items-center gap-2"
          >
            <Download className="w-4 h-4" aria-hidden />
            Download .yaml
          </button>
          {completedIdRef.current && (
            <Link
              to={`/library/${completedIdRef.current}`}
              className="px-4 py-2 rounded-lg border border-border-subtle text-sm font-medium hover:border-gray-400 inline-flex items-center gap-2 no-underline text-gray-700"
            >
              <BookMarked className="w-4 h-4" aria-hidden />
              Open in Library
            </Link>
          )}
          <button
            type="button"
            onClick={() => navigate('/')}
            className="px-4 py-2 rounded-lg border border-border-subtle text-sm font-medium hover:border-gray-400"
          >
            Back to Home
          </button>
        </div>
      )}
    </div>
  )
}
