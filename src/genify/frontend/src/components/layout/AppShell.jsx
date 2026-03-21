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
    <div className="flex min-h-screen">
      <AppSidebar />
      <MobileNavTrigger onClick={() => setMobileNavOpen(true)} />
      <MobileDrawer open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <DemoBanner />
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 min-w-0">
          {children}
        </main>
      </div>
    </div>
  )
}
