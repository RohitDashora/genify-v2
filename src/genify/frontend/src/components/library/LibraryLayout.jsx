import { Outlet, useMatch } from 'react-router-dom'
import LibraryList from './LibraryList'

export default function LibraryLayout() {
  const detailMatch = useMatch('/library/:completedId')
  const hasDetail = Boolean(detailMatch)
  const selectedId = detailMatch?.params?.completedId

  return (
    <div className="flex gap-6 min-h-0 h-full">
      <div
        className={`w-full lg:w-80 lg:shrink-0 lg:block ${hasDetail ? 'hidden' : 'block'}`}
      >
        <LibraryList selectedId={selectedId} />
      </div>

      <div className={`flex-1 min-w-0 ${hasDetail ? 'block' : 'hidden lg:block'}`}>
        {hasDetail ? (
          <Outlet />
        ) : (
          <div className="rounded-xl border border-border-subtle bg-surface shadow-card p-8 flex items-center justify-center h-64 text-gray-400 text-sm">
            Select a saved item to view
          </div>
        )}
      </div>
    </div>
  )
}
