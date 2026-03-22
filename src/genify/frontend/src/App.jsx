import { Routes, Route } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import ScrollToTop from './components/ScrollToTop'
import PageSkeleton from './components/PageSkeleton'
import NotFound from './components/NotFound'
import AppShell from './components/layout/AppShell'

const Home = lazy(() => import('./components/Home'))
const SessionView = lazy(() => import('./components/SessionView'))
const LibraryLayout = lazy(() => import('./components/library/LibraryLayout'))
const LibraryDetail = lazy(() => import('./components/library/LibraryDetail'))
const TemplatesLayout = lazy(() => import('./components/templates/TemplatesLayout'))
const TemplateDetail = lazy(() => import('./components/templates/TemplateDetail'))

export default function App() {
  return (
    <AppShell>
      <ScrollToTop />
      <div className="flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden">
        <ErrorBoundary>
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/session/:id" element={<SessionView />} />
              <Route path="/library" element={<LibraryLayout />}>
                <Route index element={null} />
                <Route path=":completedId" element={<LibraryDetail />} />
              </Route>
              <Route path="/templates" element={<TemplatesLayout />}>
                <Route index element={null} />
                <Route path="new" element={<TemplateDetail />} />
                <Route path=":templateId" element={<TemplateDetail />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </div>
    </AppShell>
  )
}
