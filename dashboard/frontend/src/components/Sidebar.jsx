import {
  BookOpen, Coins, Github, Layers, Link2, ListChecks, MessageCircle, Radio,
  Search, Settings, Settings2, Share2, Sparkles, UploadCloud, Workflow,
} from 'lucide-react'
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

// Existing operator tools that the five-destination overhaul folded into a
// hub's local tabs (Hubs.jsx SearchHub/SystemHub). Each `id` here is one of
// the existing routable view ids already wired through shellState/App.jsx —
// navigating to it opens the same existing tool view, just via a direct
// sidebar entry instead of requiring a detour through the hub's own tab bar.
const TOOL_ITEMS = [
  { id: 'memory-intake', label: 'Ingest / Add to Memory', icon: UploadCloud },
  { id: 'graphify', label: 'Graphify', icon: Share2 },
  { id: 'repo-ingest', label: 'GitHub', icon: Github },
  { id: 'workflow-bench', label: 'Workflows', icon: Workflow },
  { id: 'skills-board', label: 'Skills', icon: Sparkles },
]

const SYSTEM_ITEMS = [
  { id: 'mission-control', label: 'System Watch', icon: Radio },
  { id: 'connections-spine', label: 'Connections', icon: Link2 },
  { id: 'tokens-roi', label: 'Tokens', icon: Coins },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'prompt-library', label: 'Prompts', icon: BookOpen },
]

function SidebarGroup({ heading, items, currentView, onNavigate }) {
  return (
    <div className="mt-4 first:mt-0">
      <div className="px-2.5 pb-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-taupe/70">{heading}</div>
      {items.map(({ id, label, icon: Icon }) => {
        const active = currentView === id
        return (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            aria-label={label}
            title={label}
            aria-current={active ? 'page' : undefined}
            data-nav-tool={id}
            className={`mb-1 flex w-full items-center gap-2.5 rounded px-2.5 py-2 text-left text-sm transition-colors ${active ? 'bg-softgraph text-ivory' : 'text-taupe hover:bg-softgraph/50 hover:text-stone'}`}
          >
            <Icon size={15} className={`shrink-0 ${active ? 'text-champagne' : ''}`} />
            <span className="min-w-0 flex-1 truncate">{label}</span>
          </button>
        )
      })}
    </div>
  )
}

export default function Sidebar({ activeDestination, currentView, onNavigate, counts = {} }) {
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (counts.blocked || 0)
  return (
    <aside className="hidden w-52 flex-shrink-0 flex-col border-r border-softgraph bg-graphite md:flex" data-testid="sidebar">
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

        {/* Existing tools the overhaul buried inside Search/System hub tabs
            (Hubs.jsx). Restored as direct one-click entries so nothing that
            existed before the overhaul now takes an extra detour to reach. */}
        <SidebarGroup heading="Tools" items={TOOL_ITEMS} currentView={currentView} onNavigate={onNavigate} />
        <SidebarGroup heading="System" items={SYSTEM_ITEMS} currentView={currentView} onNavigate={onNavigate} />
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
