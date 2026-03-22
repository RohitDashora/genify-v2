import { Outlet, useMatch } from 'react-router-dom'
import TemplateList from './TemplateList'

export default function TemplatesLayout() {
  const newMatch = useMatch('/templates/new')
  const detailMatch = useMatch('/templates/:templateId')
  const hasDetail = Boolean(newMatch || detailMatch)
  const selectedId = detailMatch?.params?.templateId

  return (
    <div className="flex h-full max-h-full min-h-0 w-full flex-1 flex-col overflow-hidden rounded-xl border border-border-subtle bg-surface shadow-card">
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div
          className={`flex min-h-0 flex-col overflow-hidden p-3 sm:p-4 lg:w-80 lg:shrink-0 lg:border-r lg:border-border-subtle ${
            hasDetail ? 'hidden' : 'flex'
          } lg:flex`}
        >
          <TemplateList selectedId={selectedId} />
        </div>

        <div
          className={`min-h-0 flex flex-1 flex-col overflow-hidden p-3 sm:p-4 ${
            hasDetail ? 'flex' : 'hidden lg:flex'
          } min-w-0`}
        >
          {hasDetail ? (
            <Outlet />
          ) : (
            <div className="rounded-xl border border-dashed border-border-subtle bg-surface-muted flex flex-1 min-h-0 items-center justify-center text-gray-400 text-sm px-4">
              Select a template version
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
