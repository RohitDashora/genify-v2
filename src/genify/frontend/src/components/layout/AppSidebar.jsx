import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Sparkles, Home, BookMarked, LayoutTemplate, Menu, X } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/library', label: 'Library', icon: BookMarked },
  { to: '/templates', label: 'Templates', icon: LayoutTemplate },
]

function navClass({ isActive }) {
  return `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium no-underline transition-colors ${
    isActive
      ? 'bg-brand-50 text-brand-700'
      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
  }`
}

function SidebarContent({ onNavigate }) {
  return (
    <>
      <div className="px-4 pt-5 pb-4">
        <NavLink
          to="/"
          className="flex items-center gap-2 no-underline text-gray-800"
          onClick={onNavigate}
        >
          <Sparkles className="w-6 h-6 text-brand-500 shrink-0" aria-hidden />
          <span className="text-xl font-semibold">Genify</span>
        </NavLink>
        <p className="text-xs text-gray-500 mt-1 pl-8">Metadata Generator</p>
      </div>

      <nav className="flex-1 px-3 space-y-1" aria-label="Main">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={navClass}
            onClick={onNavigate}
          >
            <Icon className="w-4.5 h-4.5 shrink-0" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )
}

export function MobileNavTrigger({ onClick }) {
  return (
    <header className="md:hidden flex items-center gap-3 bg-surface border-b border-border-subtle px-4 py-3 shadow-sm">
      <button
        type="button"
        onClick={onClick}
        className="p-1.5 -ml-1.5 rounded-lg text-gray-600 hover:bg-gray-100"
        aria-label="Open navigation"
      >
        <Menu className="w-5 h-5" />
      </button>
      <NavLink to="/" className="flex items-center gap-2 no-underline text-gray-800">
        <Sparkles className="w-5 h-5 text-brand-500 shrink-0" aria-hidden />
        <span className="text-lg font-semibold">Genify</span>
      </NavLink>
    </header>
  )
}

export function MobileDrawer({ open, onClose }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-40 md:hidden">
      <div
        className="fixed inset-0 bg-black/20"
        onClick={onClose}
        aria-hidden
      />
      <aside className="fixed inset-y-0 left-0 w-60 bg-surface border-r border-border-subtle shadow-lg flex flex-col z-50">
        <div className="flex items-center justify-end px-3 pt-3">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <SidebarContent onNavigate={onClose} />
      </aside>
    </div>
  )
}

export default function AppSidebar() {
  return (
    <aside className="hidden md:flex md:w-60 md:shrink-0 md:flex-col bg-surface border-r border-border-subtle">
      <SidebarContent onNavigate={() => {}} />
    </aside>
  )
}
