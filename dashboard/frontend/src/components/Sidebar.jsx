import { useState } from 'react'
import { BookOpenText, Brain, ChartNoAxesCombined, ChevronLeft, ChevronRight, FolderArchive, GitBranch, LayoutDashboard, Layers, Library, ListChecks, MessageSquare, Network, Radar, Settings, Workflow, Wrench } from 'lucide-react'

export const NAV_GROUPS = [
  { label: 'Work', items: [
    { id: 'cockpit', label: 'Cockpit', icon: LayoutDashboard },
    { id: 'work-queue', label: 'Work Queue', icon: ListChecks, badge: 'needs' },
    { id: 'workflow-bench', label: 'Workflow Bench', icon: Workflow },
    { id: 'message-board', label: 'Message Board', icon: MessageSquare },
  ] },
  { label: 'Knowledge', items: [
    { id: 'skills-board', label: 'Skills Board', icon: Wrench },
    { id: 'memory-board', label: 'Memory Board', icon: Brain },
    { id: 'prompt-library', label: 'Prompt Library', icon: Library },
    { id: 'graphify', label: 'Graphify', icon: Network },
    { id: 'repo-ingest', label: 'Repo Ingest', icon: GitBranch },
  ] },
  { label: 'Evidence', items: [
    { id: 'results-receipts', label: 'Results & Receipts', icon: BookOpenText },
    { id: 'tokens-roi', label: 'Tokens & ROI', icon: ChartNoAxesCombined },
    { id: 'artifacts', label: 'Artifacts', icon: FolderArchive },
  ] },
  { label: 'System', items: [
    { id: 'connections-spine', label: 'Connections / Spine', icon: Layers },
    { id: 'mission-control', label: 'Mission Control', icon: Radar },
    { id: 'settings', label: 'Settings / Launchers', icon: Settings },
  ] },
]

export default function Sidebar({ activeView, onNavigate, counts = {} }) {
  const [collapsed, setCollapsed] = useState(false)
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (counts.blocked || 0)
  return (
    <aside className={`${collapsed ? 'w-14' : 'w-[180px]'} flex-shrink-0 flex flex-col bg-graphite border-r border-softgraph transition-[width]`} data-testid="sidebar" data-collapsed={collapsed ? 'true' : 'false'}>
      <div className="px-3 py-4 border-b border-softgraph">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded bg-champagne flex items-center justify-center">
            <Layers size={13} className="text-ivory" />
          </div>
          <div className={collapsed ? 'hidden' : ''}>
            <div className="text-xs font-semibold text-ivory tracking-wide leading-none">Agentic OS</div>
            <div className="text-[10px] text-taupe font-mono mt-0.5">Dashboard v1 · Local</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-2 py-2 overflow-y-auto">
        {NAV_GROUPS.map(group => (
          <div key={group.label} className="mb-2" data-nav-group={group.label}>
            {!collapsed && <div className="px-2 pb-1 pt-2 text-[9px] font-bold uppercase tracking-[0.16em] text-taupe">{group.label}</div>}
            {group.items.map(({ id, label, icon: Icon, badge }) => (
              <button key={id} onClick={() => onNavigate(id)} title={collapsed ? label : undefined} aria-label={label} className={`mb-0.5 flex w-full items-center ${collapsed ? 'justify-center px-2' : 'gap-2 px-2'} py-2 rounded text-xs transition-colors text-left ${activeView === id ? 'bg-softgraph text-ivory' : 'text-taupe hover:text-stone hover:bg-softgraph/50'}`}>
                <Icon size={14} className={`shrink-0 ${activeView === id ? 'text-champagne' : ''}`} />
                {!collapsed && <span className="min-w-0 flex-1 truncate font-medium">{label}</span>}
                {badge === 'needs' && needs > 0 && <span className="rounded bg-[var(--needs-review)] px-1.5 py-0.5 text-[9px] font-bold text-[var(--needs-review-text)]">{needs}</span>}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t border-softgraph p-2">
        <button onClick={() => setCollapsed(value => !value)} className="flex h-8 w-full items-center justify-center rounded text-taupe hover:bg-softgraph hover:text-stone" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          {collapsed ? <ChevronRight size={15} /> : <><ChevronLeft size={15} /><span className="ml-1 text-[10px]">Collapse</span></>}
        </button>
      </div>
    </aside>
  )
}
