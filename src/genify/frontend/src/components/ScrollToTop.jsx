import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/** Scroll primary scroll container(s) to top on client-side navigation (BrowserRouter). */
export default function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
    document.querySelector('main')?.scrollTo(0, 0)
  }, [pathname])
  return null
}
