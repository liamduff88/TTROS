import { BookOpenText, Brain, ChartNoAxesCombined, GitBranch, LayoutDashboard, Layers, Library, ListChecks, Network, Settings, Workflow, Wrench } from 'lucide-react'

const NAV = [
  { id: 'cockpit', label: 'Cockpit', icon: LayoutDashboard },
  { id: 'work-queue', label: 'Work Queue', icon: ListChecks, badge: 'needs' },
  { id: 'workflow-bench', label: 'Workflow Bench', icon: Workflow, token: true },
  { id: 'skills-board', label: 'Skills Board', icon: Wrench },
  { id: 'memory-board', label: 'Memory Board', icon: Brain, token: true },
  { id: 'graphify', label: 'Graphify', icon: Network, token: true },
  { id: 'repo-ingest', label: 'Repo Ingest', icon: GitBranch, token: true },
  { id: 'results-receipts', label: 'Results & Receipts', icon: BookOpenText },
  { id: 'tokens-roi', label: 'Tokens & ROI', icon: ChartNoAxesCombined },
  { id: 'connections-spine', label: 'Connections / Spine', icon: Layers },
  { id: 'prompt-library', label: 'Prompt Library', icon: Library },
  { id: 'settings', label: 'Settings / Launchers', icon: Settings },
]

export default function Sidebar({ activeView, onNavigate, counts = {} }) {
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (counts.blocked || 0)
  return (
    <aside className="w-64 flex-shrink-0 flex flex-col bg-graphite border-r border-softgraph">
      <div className="px-5 py-5 border-b border-softgraph">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded bg-champagne flex items-center justify-center">
            <Layers size={13} className="text-ink" />
          </div>
          <div>
            <div className="text-xs font-semibold text-ivory tracking-wide leading-none">Agentic OS</div>
            <div className="text-[10px] text-taupe font-mono mt-0.5">Dashboard v1 · Local</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV.map(({ id, label, icon: Icon, badge, token }) => (
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
            <span className="min-w-0 flex-1 truncate font-medium">{label}</span>
            {token && <span className="text-[10px] text-champagne">⚡</span>}
            {badge === 'needs' && needs > 0 && <span className="rounded bg-champagne px-1.5 py-0.5 text-[10px] font-bold text-ink">{needs}</span>}
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
            <span className="text-stone">Zero-token default</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
