import { useEffect } from 'react'
import { FileText, ScrollText, FolderOpen, DollarSign, Bot, Clock, Zap, Target, Gauge } from 'lucide-react'

const MetricCard = ({ label, value, sub, icon: Icon, accent }) => (
  <div className="bg-graphite border border-softgraph rounded-lg p-5">
    <div className="flex items-start justify-between mb-3">
      <span className="text-xs text-taupe font-medium uppercase tracking-wider">{label}</span>
      <Icon size={14} className={accent || 'text-taupe'} />
    </div>
    <div className={`text-2xl font-mono font-semibold ${accent || 'text-ivory'}`}>{value}</div>
    {sub && <div className="text-xs text-taupe mt-1">{sub}</div>}
  </div>
)

const AgentStatusRow = ({ name, status, statusLabel }) => {
  const dot = {
    not_connected: 'bg-taupe',
    setup_pending: 'bg-taupe',
    browser_only: 'bg-olive',
    placeholder: 'bg-taupe',
    installed: 'bg-champagne',
    local: 'bg-olive',
  }[status] || 'bg-taupe'

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-softgraph last:border-0">
      <span className="text-sm text-stone font-medium">{name}</span>
      <div className="flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full ${dot}`} />
        <span className="text-xs font-mono text-taupe">{statusLabel}</span>
      </div>
    </div>
  )
}

const AGENTS = [
  { name: 'Claude Code', status: 'installed', statusLabel: 'Live via AgenticOSClean' },
  { name: 'Codex', status: 'installed', statusLabel: 'Live via AgenticOSClean' },
  { name: 'Hermes', status: 'installed', statusLabel: 'Live router via AgenticOSClean' },
  { name: 'Antigravity', status: 'local', statusLabel: 'Windows dashboard builder/operator UI' },
  { name: 'ChatGPT', status: 'browser_only', statusLabel: 'Browser/operator strategy' },
  { name: 'Local Vault', status: 'local', statusLabel: 'Agentic OS Live only' },
  { name: 'Old Ubuntu', status: 'placeholder', statusLabel: 'Archive only' },
]

export default function Overview({ overview, onNavigate, onRefresh }) {
  useEffect(() => {
    onRefresh?.()
  }, [])

  const tokenUsage = overview?.tokenUsage
  const tokenText = tokenUsage?.last_task_token_usage_text?.replace(/^Token usage:\s*/i, '') || 'no task recorded'
  const tokenAgent = tokenUsage?.last_task_route || 'No task recorded'
  const tokenTimestamp = tokenUsage?.last_task_timestamp
    ? new Date(tokenUsage.last_task_timestamp).toLocaleString()
    : 'No timestamp available'
  const recentActivity = tokenUsage?.recent_activity || overview?.recent_activity || []
  const formatTokens = value => Number(value || 0).toLocaleString()

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold text-ivory mb-1">Operator Overview</h1>
        <p className="text-sm text-taupe">Agentic OS v0.1 — local cockpit, model-silent</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Task Packets"
          value={overview?.totalPackets ?? '—'}
          sub="saved locally"
          icon={FileText}
          accent="text-champagne"
        />
        <MetricCard
          label="Log Entries"
          value={overview?.totalLogs ?? '—'}
          sub="in /logs"
          icon={ScrollText}
        />
        <MetricCard
          label="Results"
          value={overview?.totalResults ?? '—'}
          sub="in /results"
          icon={FolderOpen}
        />
        <MetricCard
          label="Est. Value"
          value={overview?.estimatedValue ? `$${overview.estimatedValue.toLocaleString()}` : '$0'}
          sub="from tracker"
          icon={DollarSign}
          accent={overview?.estimatedValue > 0 ? 'text-champagne' : 'text-taupe'}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-graphite border border-softgraph rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-stone uppercase tracking-wider">Agent Status Board</h2>
            <Bot size={13} className="text-taupe" />
          </div>
          {AGENTS.map(a => <AgentStatusRow key={a.name} {...a} />)}
          <p className="text-xs text-taupe mt-4 font-mono">Live runtime: AgenticOSClean · Windows operator: Antigravity</p>
        </div>

        <div className="space-y-4">
          <div className="bg-graphite border border-softgraph rounded-lg p-5">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={13} className="text-champagne" />
              <h2 className="text-sm font-semibold text-stone uppercase tracking-wider">Quick Actions</h2>
            </div>
            <div className="space-y-2">
              {[
                { label: 'Create Task Packet', view: 'packets' },
                { label: 'Open Agent Workbench', view: 'agents' },
                { label: 'Update Value Tracker', view: 'tracker' },
                { label: 'View Logs', view: 'logs' },
              ].map(({ label, view }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => onNavigate?.(view)}
                  className="w-full text-left text-xs text-taupe py-1.5 border-b border-softgraph last:border-0 font-medium hover:text-stone transition-colors"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-graphite border border-softgraph rounded-lg p-5">
            <div className="flex items-center gap-2 mb-3">
              <Target size={13} className="text-taupe" />
              <h2 className="text-sm font-semibold text-stone uppercase tracking-wider">System</h2>
            </div>
            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between text-taupe">
                <span>Mode</span>
                <span className="text-stone">Model-silent</span>
              </div>
              <div className="flex justify-between text-taupe">
                <span>Token reporting</span>
                <span className="text-stone">Tracked below</span>
              </div>
              <div className="flex justify-between text-taupe">
                <span>Backend</span>
                <span className="text-champagne">:8010</span>
              </div>
              <div className="flex justify-between text-taupe">
                <span>Frontend</span>
                <span className="text-champagne">:3010</span>
              </div>
              <div className="flex justify-between text-taupe">
                <span>Version</span>
                <span className="text-stone">0.1.0</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-graphite border border-softgraph rounded-lg p-5">
        <div className="flex items-center gap-2 mb-3">
          <Gauge size={13} className="text-champagne" />
          <h2 className="text-sm font-semibold text-stone uppercase tracking-wider">Token Usage</h2>
        </div>
        <div className="text-xs uppercase tracking-wider text-taupe">Last task token usage</div>
        <div className="text-lg font-mono text-ivory">{tokenText}</div>
        <div className="mt-4 grid grid-cols-3 gap-4 text-xs font-mono">
          <div><div className="text-taupe">Today known tokens</div><div className="text-stone text-base">{formatTokens(tokenUsage?.known_tokens_today)}</div></div>
          <div><div className="text-taupe">This week known tokens</div><div className="text-stone text-base">{formatTokens(tokenUsage?.known_tokens_this_week)}</div></div>
          <div><div className="text-taupe">This month known tokens</div><div className="text-stone text-base">{formatTokens(tokenUsage?.known_tokens_this_month)}</div></div>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs font-mono text-taupe">
          <span>Route: <span className="text-stone">{tokenAgent}</span></span>
          <span>Timestamp: <span className="text-stone">{tokenTimestamp}</span></span>
          {tokenUsage?.unavailable_count_today > 0 && <span>Unavailable today: <span className="text-clay">{tokenUsage.unavailable_count_today}</span></span>}
        </div>
      </div>

      <div className="bg-graphite border border-softgraph rounded-lg p-5">
        <div className="flex items-center gap-2 mb-3">
          <Clock size={13} className="text-taupe" />
          <h2 className="text-sm font-semibold text-stone uppercase tracking-wider">Recent Activity</h2>
        </div>
        {recentActivity.length ? (
          <div className="divide-y divide-softgraph">
            {recentActivity.map((activity, index) => (
              <div key={`${activity.timestamp}-${index}`} className="grid grid-cols-[10rem_7rem_7rem_1fr] gap-3 py-2.5 text-xs font-mono">
                <span className="text-taupe">{activity.timestamp ? new Date(activity.timestamp).toLocaleString() : 'Unknown time'}</span>
                <span className="text-stone">{activity.route || activity.agent || 'unknown'}</span>
                <span className="text-taupe">{activity.status || 'recorded'}</span>
                <span className="min-w-0 text-taupe">
                  <span className="text-stone">{activity.token_usage_text?.replace(/^Token usage:\s*/i, '') || 'unavailable'}</span>
                  {activity.task && <span className="block truncate mt-0.5" title={activity.task}>{activity.task}</span>}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-taupe font-mono text-center py-6">No activity recorded.</div>
        )}
      </div>
    </div>
  )
}
