import { Component } from 'react'
import { MessageCircleWarning } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-lg mx-auto mt-12 rounded-xl border border-danger-200 bg-danger-50 p-6 text-danger-800 shadow-card">
          <div className="flex items-center gap-2 font-medium">
            <MessageCircleWarning className="w-5 h-5 shrink-0" aria-hidden />
            Something went wrong
          </div>
          <p className="text-sm mt-2 text-danger-800">{this.state.error.message}</p>
          <button
            type="button"
            className="mt-4 text-sm px-3 py-1.5 rounded-lg border border-danger-300 hover:bg-danger-100"
            onClick={() => window.location.reload()}
          >
            Reload page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
