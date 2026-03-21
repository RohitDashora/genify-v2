/**
 * Persistent notice: this repository is a reference / demo app, not a production product.
 */
export default function DemoBanner() {
  return (
    <div
      className="shrink-0 border-b border-amber-200/90 bg-amber-50 px-4 py-2 text-center text-sm text-amber-950 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-100"
      role="status"
    >
      <span className="font-medium">Demo / reference app</span>
      <span className="mx-1.5 text-amber-800/80 dark:text-amber-200/80">—</span>
      For learning and evaluation. Not supported or warranted for production use.
    </div>
  )
}
