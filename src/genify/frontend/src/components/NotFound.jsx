import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="max-w-md mx-auto text-center py-16 px-4">
      <p className="text-sm font-medium text-gray-500">404</p>
      <h1 className="mt-2 text-xl font-semibold text-gray-900">Page not found</h1>
      <p className="mt-2 text-sm text-gray-600">
        That URL doesn&apos;t match anything in Genify.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600 no-underline"
      >
        <Home className="w-4 h-4 shrink-0" aria-hidden />
        Back to home
      </Link>
    </div>
  )
}
