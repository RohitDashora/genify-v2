import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Agent / plan message body — GFM, no raw HTML. */
export default function TranscriptMarkdown({ children }) {
  if (!children) return null
  return (
    <div className="prose prose-sm prose-slate max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
        {children}
      </ReactMarkdown>
    </div>
  )
}
