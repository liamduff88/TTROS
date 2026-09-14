import { Layers, ListChecks, MessageCircle, Search, Settings2 } from 'lucide-react'
import { DESTINATIONS } from '../shellState'

// One icon per global destination, shared by the desktop Sidebar and the
// mobile bottom nav so both surfaces always agree on the five destinations
// (BUILD_SPECIFICATION "Global navigation and shell").
const DESTINATION_ICONS = {
  cockpit: MessageCircle,
  'work-queue': ListChecks,
  results: Layers,
  search: Search,
  system: Settings2,
}

export const NAV_ITEMS = DESTINATIONS.map(destination => ({ ...destination, icon: DESTINATION_ICONS[destination.id] }))

export default function Sidebar({ activeDestination, onNavigate, counts = {} }) {
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (counts.blocked || 0)
  return (
    <aside className="hidden w-48 flex-shrink-0 flex-col border-r border-softgraph bg-graphite md:flex" data-testid="sidebar">
      <div className="border-b border-softgraph px-3 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-champagne">
            <Layers size={13} className="text-ivory" />
          </div>
          <div>
            <div className="text-xs font-semibold leading-none tracking-wide text-ivory">Agentic OS</div>
            <div className="mt-0.5 font-mono text-[10px] text-taupe">Dashboard · Local</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Global destinations">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active = activeDestination === id
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              aria-label={label}
              aria-current={active ? 'page' : undefined}
              data-nav-destination={id}
              className={`mb-1 flex w-full items-center gap-2.5 rounded px-2.5 py-2.5 text-left text-sm transition-colors ${active ? 'bg-softgraph text-ivory' : 'text-taupe hover:bg-softgraph/50 hover:text-stone'}`}
            >
              <Icon size={16} className={`shrink-0 ${active ? 'text-champagne' : ''}`} />
              <span className="min-w-0 flex-1 truncate font-medium">{label}</span>
              {id === 'work-queue' && needs > 0 && <span className="rounded bg-[var(--needs-review)] px-1.5 py-0.5 text-[9px] font-bold text-[var(--needs-review-text)]">{needs}</span>}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

// Fixed, safe-area-aware bottom navigation for <768px (BUILD_SPECIFICATION
// "Mobile" layout order + "Global navigation and shell"). Never rendered
// alongside the desktop Sidebar — App.jsx shows exactly one of the two.
export function MobileNav({ activeDestination, onNavigate, counts = {} }) {
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (counts.blocked || 0)
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-softgraph bg-graphite md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      aria-label="Global destinations"
      data-testid="mobile-nav"
    >
      {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
        const active = activeDestination === id
        return (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            aria-label={label}
            aria-current={active ? 'page' : undefined}
            data-nav-destination={id}
            className={`relative flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium ${active ? 'text-champagne' : 'text-taupe'}`}
          >
            <Icon size={18} />
            <span>{label}</span>
            {id === 'work-queue' && needs > 0 && (
              <span className="absolute right-[22%] top-1 rounded-full bg-[var(--needs-review)] px-1 text-[9px] font-bold leading-tight text-[var(--needs-review-text)]">{needs}</span>
            )}
          </button>
        )
      })}
    </nav>
  )
}
