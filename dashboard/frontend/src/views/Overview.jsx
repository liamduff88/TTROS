import { useEffect } from 'react'
import {
  Activity,
  Bot,
  Cable,
  Clock,
  Code2,
  FileText,
  FolderOpen,
  Gauge,
  LayoutDashboard,
  Play,
  Route,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Terminal,
  Wrench,
} from 'lucide-react'

const formatCount = value => Number(value || 0).toLocaleString()

const formatTimestamp = value => {
  if (!value) return 'No timestamp'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown time' : date.toLocaleString()
}

const cleanTokenText = value => value?.replace(/^Token usage:\s*/i, '') || 'unavailable'

const statusTone = {
  ready: { dot: 'bg-champagne', text: 'text-champagne', border: 'border-champagne/40' },
  local: { dot: 'bg-olive', text: 'text-olive', border: 'border-olive/40' },
  unavailable: { dot: 'bg-taupe', text: 'text-taupe', border: 'border-softgraph' },
}

const LaunchTile = ({ title, description, icon: Icon, action, tone = 'ready', onClick }) => {
  const sc = statusTone[tone] || statusTone.ready

  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex min-h-[8.5rem] flex-col justify-between rounded-lg border ${sc.border} bg-graphite p-5 text-left transition-colors hover:border-champagne/70 hover:bg-softgraph/50`}
    >
      <div className="flex items-start justify-between gap-4">
        <Icon size={18} className={sc.text} />
        <Play size={14} className="text-taupe transition-colors group-hover:text-champagne" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-ivory">{title}</h2>
        <p className="mt-1 text-sm leading-snug text-taupe">{description}</p>
        <div className="mt-3 text-xs font-mono uppercase tracking-wider text-stone">{action}</div>
      </div>
    </button>
  )
}

const SummaryCard = ({ label, value, sub, icon: Icon, accent = 'text-stone' }) => (
  <div className="rounded-lg border border-softgraph bg-graphite p-4">
    <div className="mb-3 flex items-start justify-between gap-3">
      <span className="text-xs font-medium uppercase tracking-wider text-taupe">{label}</span>
      <Icon size={14} className={accent} />
    </div>
    <div className={`text-2xl font-mono font-semibold ${accent}`}>{value}</div>
    {sub && <div className="mt-1 text-xs text-taupe">{sub}</div>}
  </div>
)

const AgentCard = ({ name, role, state, stateLabel, detail, icon: Icon }) => {
  const sc = statusTone[state] || statusTone.unavailable

  return (
    <div className="rounded-lg border border-softgraph bg-graphite p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon size={14} className={sc.text} />
          <h3 className="text-sm font-semibold text-ivory">{name}</h3>
        </div>
        <div className={`mt-1 h-2 w-2 rounded-full ${sc.dot}`} />
      </div>
      <div className="text-xs text-taupe">{role}</div>
      <div className={`mt-3 text-[11px] font-mono uppercase tracking-wider ${sc.text}`}>{stateLabel}</div>
      <div className="mt-1 text-xs leading-snug text-taupe">{detail}</div>
    </div>
  )
}

const QuickLink = ({ label, sub, icon: Icon, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="flex w-full items-center justify-between gap-3 border-b border-softgraph py-3 text-left last:border-0"
  >
    <div className="flex min-w-0 items-center gap-3">
      <Icon size={14} className="flex-shrink-0 text-taupe" />
      <div className="min-w-0">
        <div className="text-sm font-medium text-stone">{label}</div>
        <div className="truncate text-xs text-taupe">{sub}</div>
      </div>
    </div>
    <Route size={13} className="flex-shrink-0 text-taupe" />
  </button>
)

export default function Overview({ overview, onNavigate, onRefresh }) {
  useEffect(() => {
    onRefresh?.()
  }, [])

  const tokenUsage = overview?.tokenUsage
  const recentActivity = tokenUsage?.recent_activity || overview?.recent_activity || []
  const lastTokenText = cleanTokenText(tokenUsage?.last_task_token_usage_text)
  const lastRoute = tokenUsage?.last_task_route || 'No route recorded'
  const lastTimestamp = formatTimestamp(tokenUsage?.last_task_timestamp)
  const hasTokenData = Boolean(tokenUsage)
  const hasRecentActivity = recentActivity.length > 0
  const packets = overview?.totalPackets
  const logs = overview?.totalLogs
  const results = overview?.totalResults
  const estimatedValue = overview?.estimatedValue || 0

  const agentCards = [
    {
      name: 'Hermes',
      role: 'Router and launch path',
      state: 'ready',
      stateLabel: 'Workbench route',
      detail: 'Use Agent Workbench for Hermes status and routed task execution.',
      icon: Sparkles,
    },
    {
      name: 'Codex',
      role: 'Coding agent',
      state: 'ready',
      stateLabel: 'Workbench route',
      detail: 'Direct run controls live inside the existing Agent Workbench.',
      icon: Code2,
    },
    {
      name: 'Claude',
      role: 'Alternate coding agent',
      state: 'ready',
      stateLabel: 'Workbench route',
      detail: 'Available through the existing Hermes run panel when backend supports it.',
      icon: Bot,
    },
    {
      name: 'Dashboard',
      role: 'Local operator UI',
      state: 'local',
      stateLabel: 'Active',
      detail: 'This cockpit keeps navigation and read-only local state in one place.',
      icon: LayoutDashboard,
    },
    {
      name: 'Connectors',
      role: 'External system controls',
      state: 'unavailable',
      stateLabel: 'Open status route',
      detail: 'Status is checked in Connectors via existing backend routes only.',
      icon: Cable,
    },
  ]

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-champagne">Agentic OS Cockpit</p>
          <h1 className="mt-1 text-2xl font-semibold text-ivory">Operator Front Door</h1>
          <p className="mt-1 text-sm text-taupe">Launch work, inspect state, and route into the existing dashboard controls.</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone"
        >
          <Activity size={13} />
          Refresh overview
        </button>
      </div>

      <section className="grid gap-4 lg:grid-cols-3">
        <LaunchTile
          title="Launch Workbench"
          description="Open Hermes, Codex, and Claude controls in the existing agent surface."
          action="Primary command area"
          icon={Terminal}
          onClick={() => onNavigate?.('agents')}
        />
        <LaunchTile
          title="Create Task Packet"
          description="Draft a local packet before handing work to an agent."
          action="Packet creator"
          icon={FileText}
          tone="local"
          onClick={() => onNavigate?.('packets')}
        />
        <LaunchTile
          title="Check Connectors"
          description="Review connector status and controls through existing backend routes."
          action="Connector controls"
          icon={Cable}
          tone="unavailable"
          onClick={() => onNavigate?.('connectors')}
        />
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard label="Packets" value={packets ?? '-'} sub="saved locally" icon={FileText} accent="text-champagne" />
        <SummaryCard label="Logs" value={logs ?? '-'} sub="available in logs/results" icon={ScrollText} />
        <SummaryCard label="Results" value={results ?? '-'} sub="completed outputs" icon={FolderOpen} />
        <SummaryCard
          label="Estimated Value"
          value={`$${formatCount(estimatedValue)}`}
          sub="from tracker"
          icon={Gauge}
          accent={estimatedValue > 0 ? 'text-champagne' : 'text-taupe'}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Agent Status</h2>
            <ShieldCheck size={14} className="text-taupe" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {agentCards.map(agent => <AgentCard key={agent.name} {...agent} />)}
          </div>
        </div>

        <div className="space-y-4 lg:col-span-2">
          <div className="rounded-lg border border-softgraph bg-graphite p-5">
            <div className="mb-3 flex items-center gap-2">
              <Gauge size={14} className="text-champagne" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Token Status</h2>
            </div>
            {hasTokenData ? (
              <>
                <div className="text-lg font-mono text-ivory">{lastTokenText}</div>
                <div className="mt-3 grid grid-cols-3 gap-3 text-xs font-mono">
                  <div>
                    <div className="text-taupe">Today</div>
                    <div className="text-stone">{formatCount(tokenUsage?.known_tokens_today)}</div>
                  </div>
                  <div>
                    <div className="text-taupe">Week</div>
                    <div className="text-stone">{formatCount(tokenUsage?.known_tokens_this_week)}</div>
                  </div>
                  <div>
                    <div className="text-taupe">Month</div>
                    <div className="text-stone">{formatCount(tokenUsage?.known_tokens_this_month)}</div>
                  </div>
                </div>
                <div className="mt-3 space-y-1 text-xs font-mono text-taupe">
                  <div>Route: <span className="text-stone">{lastRoute}</span></div>
                  <div>Updated: <span className="text-stone">{lastTimestamp}</span></div>
                </div>
              </>
            ) : (
              <div className="rounded border border-softgraph bg-ink px-4 py-5 text-center text-xs font-mono text-taupe">
                Token data unavailable. Connect the backend overview source to populate this panel.
              </div>
            )}
          </div>

          <div className="rounded-lg border border-softgraph bg-graphite p-5">
            <div className="mb-1 flex items-center gap-2">
              <Wrench size={14} className="text-taupe" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Quick Links</h2>
            </div>
            <QuickLink label="Logs and results" sub={`${logs ?? '-'} logs, ${results ?? '-'} results`} icon={ScrollText} onClick={() => onNavigate?.('logs')} />
            <QuickLink label="Connector controls" sub="Open status and refresh controls" icon={Cable} onClick={() => onNavigate?.('connectors')} />
            <QuickLink label="Time and value" sub={`Current estimate $${formatCount(estimatedValue)}`} icon={Gauge} onClick={() => onNavigate?.('tracker')} />
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-softgraph bg-graphite p-5">
        <div className="mb-3 flex items-center gap-2">
          <Clock size={14} className="text-taupe" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Recent Activity</h2>
        </div>
        {hasRecentActivity ? (
          <div className="divide-y divide-softgraph">
            {recentActivity.slice(0, 6).map((activity, index) => (
              <div key={`${activity.timestamp || 'activity'}-${index}`} className="grid gap-2 py-3 text-xs font-mono md:grid-cols-[10rem_8rem_7rem_1fr]">
                <span className="text-taupe">{formatTimestamp(activity.timestamp)}</span>
                <span className="text-stone">{activity.route || activity.agent || 'unknown'}</span>
                <span className="text-taupe">{activity.status || 'recorded'}</span>
                <span className="min-w-0 text-taupe">
                  <span className="text-stone">{cleanTokenText(activity.token_usage_text)}</span>
                  {activity.task && <span className="mt-0.5 block truncate" title={activity.task}>{activity.task}</span>}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">
            No workflow history available yet.
          </div>
        )}
      </section>
    </div>
  )
}
