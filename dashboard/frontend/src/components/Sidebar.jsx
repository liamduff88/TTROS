import { LayoutDashboard, Bot, FileText, TrendingUp, ScrollText, Layers } from 'lucide-react'

const NAV = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'agents', label: 'Agent Workbench', icon: Bot },
  { id: 'packets', label: 'Packet Creator', icon: FileText },
  { id: 'tracker', label: 'Time & Value', icon: TrendingUp },
  { id: 'logs', label: 'Logs & Results', icon: ScrollText },
  { id: 'connectors', label: 'Connectors', icon: Layers },
]

export default function Sidebar({ activeView, onNavigate }) {
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-graphite border-r border-softgraph">
      <div className="px-5 py-5 border-b border-softgraph">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded bg-champagne flex items-center justify-center">
            <Layers size={13} className="text-ink" />
          </div>
          <div>
            <div className="text-xs font-semibold text-ivory tracking-wide leading-none">Agentic OS</div>
            <div className="text-[10px] text-taupe font-mono mt-0.5">v0.1 · Local</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-sm transition-colors duration-100 text-left ${
              activeView === id
                ? 'bg-softgraph text-ivory'
                : 'text-taupe hover:text-stone hover:bg-softgraph/50'
            }`}
          >
            <Icon size={14} className={activeView === id ? 'text-champagne' : ''} />
            <span className="font-medium">{label}</span>
          </button>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-softgraph">
        <div className="text-[10px] text-taupe font-mono space-y-1">
          <div className="flex justify-between">
            <span>Backend</span>
            <span className="text-champagne">:8010</span>
          </div>
          <div className="flex justify-between">
            <span>Frontend</span>
            <span className="text-champagne">:3010</span>
          </div>
          <div className="flex justify-between">
            <span>Mode</span>
            <span className="text-stone">Model-silent</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
