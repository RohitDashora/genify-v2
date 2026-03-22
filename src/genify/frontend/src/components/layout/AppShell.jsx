import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import AppSidebar, { MobileNavTrigger, MobileDrawer } from './AppSidebar'
import DemoBanner from './DemoBanner'

export default function AppShell({ children }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    setMobileNavOpen(false)
  }, [pathname])

  return (
    <div className="flex h-dvh max-h-dvh min-h-0 w-full overflow-hidden">
      <AppSidebar />
      <MobileNavTrigger onClick={() => setMobileNavOpen(true)} />
      <MobileDrawer open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <DemoBanner />
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-6 min-w-0 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  )
}
