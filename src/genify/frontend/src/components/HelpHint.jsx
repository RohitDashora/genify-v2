import { useId } from 'react'
import { HelpCircle } from 'lucide-react'

/**
 * Contextual help tooltip: small ? icon that reveals help text on hover/focus.
 *
 * @param {{ label: string, children: React.ReactNode, className?: string }} props
 *   - label: accessible name (e.g. "About: Catalog browser")
 *   - children: short help text (1–3 sentences)
 */
export default function HelpHint({ label, children, className = '' }) {
  const tipId = useId()

  return (
    <span className={`relative inline-flex items-center group ${className}`}>
      <button
        type="button"
        className="p-0.5 rounded text-gray-400 hover:text-gray-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-500"
        aria-label={label}
        aria-describedby={tipId}
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>
      <span
        id={tipId}
        role="tooltip"
        className="
          pointer-events-none absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50
          w-max max-w-xs px-3 py-2 rounded-lg
          border border-border-subtle bg-surface shadow-card
          text-xs text-gray-700 leading-relaxed
          opacity-0 invisible
          transition-opacity duration-150
          group-hover:opacity-100 group-hover:visible
          group-focus-within:opacity-100 group-focus-within:visible
        "
      >
        {children}
      </span>
    </span>
  )
}
