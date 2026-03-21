/** Suspense fallback matching Home layout (2 cols + session list). */
export default function PageSkeleton() {
  const pulse = 'animate-pulse rounded-lg bg-gray-200/80'
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-w-0" aria-busy="true" aria-label="Loading page">
      <div className="lg:col-span-2 space-y-6">
        <div className={`${pulse} h-64 w-full`} />
        <div className={`${pulse} h-48 w-full`} />
      </div>
      <div className={`${pulse} h-96 w-full`} />
    </div>
  )
}
