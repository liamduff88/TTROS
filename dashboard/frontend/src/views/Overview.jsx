import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertCircle,
  Bot,
  Cable,
  CheckCircle2,
  Clock,
  Code2,
  FileText,
  FolderOpen,
  Gauge,
  LayoutDashboard,
  ListChecks,
  Loader2,
  Play,
  Route,
  ScrollText,
  Server,
  ShieldCheck,
  Sparkles,
  Terminal,
  Wrench,
} from 'lucide-react'
import { getHealth, getQueueSummary, wslStatus } from '../api'

const formatCount = value => Number(value || 0).toLocaleString()
const TOKEN_UNAVAILABLE_TEXT = 'Token usage: unavailable from current CLI output'

const formatTimestamp = value => {
  if (!value) return 'No timestamp'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown time' : date.toLocaleString()
}

const cleanTokenText = value => {
  if (!value) return TOKEN_UNAVAILABLE_TEXT
  if (/no task recorded/i.test(value)) return TOKEN_UNAVAILABLE_TEXT
  return value.replace(/^Token usage:\s*/i, 'Token usage: ')
}

const hasKnownPeriodTotal = (tokenUsage, key) => {
  if (!tokenUsage) return false
  if (key === 'known_tokens_today') return Boolean(tokenUsage.has_known_tokens_today)
  if (key === 'known_tokens_this_week') return Boolean(tokenUsage.has_known_tokens_this_week)
  if (key === 'known_tokens_this_month') return Boolean(tokenUsage.has_known_tokens_this_month)
  return false
}

const formatTokenTotal = (tokenUsage, key) => (
  hasKnownPeriodTotal(tokenUsage, key) ? formatCount(tokenUsage?.[key]) : 'Unavailable'
)

const compactStatusDetail = value => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return ''
  return text.length > 140 ? `${text.slice(0, 137).trim()}...` : text
}

const statusTone = {
  ready: { dot: 'bg-champagne', text: 'text-champagne', border: 'border-champagne/40' },
  local: { dot: 'bg-olive', text: 'text-olive', border: 'border-olive/40' },
  loading: { dot: 'bg-taupe animate-pulse', text: 'text-taupe', border: 'border-softgraph' },
  error: { dot: 'bg-clay', text: 'text-clay', border: 'border-clay/40' },
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

const SummaryCard = ({ label, value, sub, icon: Icon, accent = 'text-stone', className = '' }) => (
  <div className={`rounded-lg border border-softgraph bg-graphite p-4 ${className}`}>
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

const StatusCard = ({ name, role, state, stateLabel, detail, icon: Icon }) => {
  const sc = statusTone[state] || statusTone.unavailable
  const StateIcon = state === 'loading' ? Loader2 : state === 'error' ? AlertCircle : state === 'ready' || state === 'local' ? CheckCircle2 : AlertCircle

  return (
    <div className={`rounded-lg border ${sc.border} bg-graphite p-4`}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon size={14} className={sc.text} />
          <h3 className="text-sm font-semibold text-ivory">{name}</h3>
        </div>
        <StateIcon size={14} className={`${sc.text} ${state === 'loading' ? 'animate-spin' : ''}`} />
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

const QueueOverviewCard = ({ state = {} }) => {
  const data = state.data || {}
  const topItem = data.topActiveItem || data.nextItem
  const hasError = state.status === 'error' || data.success === false
  const tokenNote = data.token_usage || 'no agent invocation'

  return (
    <div className="rounded-lg border border-softgraph bg-graphite p-4">
      <div className="mb-3 flex items-center gap-2">
        <ListChecks size={14} className="text-champagne" />
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Queue Visibility</h2>
          <div className="mt-0.5 text-[11px] font-mono text-taupe">Local status only; no agent launched.</div>
        </div>
      </div>

      {state.status === 'loading' ? (
        <div className="rounded border border-softgraph bg-ink px-4 py-5 text-center text-xs font-mono text-taupe">
          Loading local queue.
        </div>
      ) : hasError ? (
        <div className="rounded border border-clay/40 bg-clay/10 px-4 py-5 text-center text-xs font-mono text-stone">
          Queue unavailable.
        </div>
      ) : (
        <>
          <div className="text-sm font-medium text-ivory">{data.nextAction || 'Add a queue item or continue normal Hermes work.'}</div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-xs font-mono">
            <div>
              <div className="text-taupe">Active</div>
              <div className="text-stone">{formatCount(data.activeCount)}</div>
            </div>
            <div>
              <div className="text-taupe">Review</div>
              <div className="text-stone">{formatCount(data.needsReviewCount ?? ((data.counts?.needs_input || 0) + (data.counts?.human_review || 0)))}</div>
            </div>
            <div>
              <div className="text-taupe">Blocked</div>
              <div className="text-stone">{formatCount(data.blockedCount ?? data.counts?.blocked)}</div>
            </div>
          </div>
          <div className="mt-4 rounded border border-softgraph bg-ink p-3 text-xs">
            <div className="font-mono uppercase tracking-wider text-taupe">Top active item</div>
            {topItem ? (
              <div className="mt-2 space-y-1">
                <div className="font-semibold text-ivory">{topItem.id} | {topItem.title || 'Untitled queue item'}</div>
                <div className="font-mono text-taupe">
                  {topItem.owner || 'unassigned'} | {String(topItem.status || '').replace(/_/g, ' ')}
                </div>
              </div>
            ) : (
              <div className="mt-2 font-mono text-taupe">No active queue items.</div>
            )}
          </div>
          <div className="mt-3 text-xs font-mono text-taupe">Token usage: {tokenNote}</div>
        </>
      )}
    </div>
  )
}

const TokenStatusCard = ({ loading, error, tokenUsage, lastTokenText, lastRoute, lastTimestamp }) => (
  <div className="rounded-lg border border-softgraph bg-graphite p-4">
    <div className="mb-3 flex items-center gap-2">
      <Gauge size={14} className="text-champagne" />
      <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Token Burn</h2>
    </div>
    {loading ? (
      <div className="rounded border border-softgraph bg-ink px-4 py-5 text-center text-xs font-mono text-taupe">
        Loading token status from overview.
      </div>
    ) : error || !tokenUsage ? (
      <div className="rounded border border-softgraph bg-ink px-4 py-5 text-center text-xs font-mono text-taupe">
        {TOKEN_UNAVAILABLE_TEXT}
      </div>
    ) : (
      <>
        <div className="text-base font-mono text-ivory">{lastTokenText}</div>
        <div className="mt-3 grid grid-cols-3 gap-3 text-xs font-mono">
          <div>
            <div className="text-taupe">Today</div>
            <div className="text-stone">{formatTokenTotal(tokenUsage, 'known_tokens_today')}</div>
          </div>
          <div>
            <div className="text-taupe">Week</div>
            <div className="text-stone">{formatTokenTotal(tokenUsage, 'known_tokens_this_week')}</div>
          </div>
          <div>
            <div className="text-taupe">Month</div>
            <div className="text-stone">{formatTokenTotal(tokenUsage, 'known_tokens_this_month')}</div>
          </div>
        </div>
        <div className="mt-3 space-y-1 text-xs font-mono text-taupe">
          <div>Route: <span className="text-stone">{lastRoute}</span></div>
          <div>Updated: <span className="text-stone">{lastTimestamp}</span></div>
        </div>
      </>
    )}
  </div>
)

export default function Overview({ overview, onNavigate, onRefresh }) {
  const [backendState, setBackendState] = useState({ status: 'loading', data: null, error: null })
  const [wslState, setWslState] = useState({ status: 'loading', data: null, error: null })
  const [queueState, setQueueState] = useState({ status: 'loading', data: null, error: null })

  const refreshStatus = () => {
    setBackendState(current => ({ ...current, status: 'loading', error: null }))
    setWslState(current => ({ ...current, status: 'loading', error: null }))
    setQueueState(current => ({ ...current, status: 'loading', error: null }))

    getHealth()
      .then(data => setBackendState({ status: 'ready', data, error: null }))
      .catch(error => setBackendState({ status: 'error', data: null, error }))

    wslStatus()
      .then(data => setWslState({ status: data?.success ? 'ready' : 'error', data, error: null }))
      .catch(error => setWslState({ status: 'error', data: null, error }))

    getQueueSummary()
      .then(data => setQueueState({ status: data?.success === false ? 'error' : 'ready', data, error: null }))
      .catch(error => setQueueState({ status: 'error', data: null, error }))
  }

  useEffect(() => {
    onRefresh?.()
    refreshStatus()
  }, [])

  const safeOverview = overview || {}
  const tokenUsage = safeOverview.tokenUsage
  const recentActivitySource = tokenUsage?.recent_activity || safeOverview.recent_activity
  const recentActivity = Array.isArray(recentActivitySource) ? recentActivitySource : []
  const lastTokenText = cleanTokenText(tokenUsage?.last_task_token_usage_text)
  const lastRoute = tokenUsage?.last_task_route || 'No route recorded'
  const lastTimestamp = formatTimestamp(tokenUsage?.last_task_timestamp)
  const hasRecentActivity = recentActivity.length > 0
  const packets = safeOverview.totalPackets ?? 0
  const logs = safeOverview.totalLogs ?? 0
  const results = safeOverview.totalResults ?? 0
  const estimatedValue = safeOverview.estimatedValue || 0
  const overviewLoading = !overview
  const overviewError = Boolean(safeOverview.error)
  const backendReady = backendState.status === 'ready'
  const wslReady = wslState.status === 'ready'
  const wslOutput = wslState.data?.output || wslState.error?.response?.data?.detail || wslState.error?.message
  const routeState = wslState.status === 'loading' ? 'loading' : wslReady ? 'ready' : 'error'
  const routeLabel = wslState.status === 'loading' ? 'Checking route' : wslReady ? 'Clean WSL route' : 'Route unavailable'
  const routeDetail = wslState.status === 'loading'
    ? 'Checking AgenticOSClean through the existing WSL status route.'
    : wslReady
      ? 'Targets AgenticOSClean backend routes; launch controls stay in Agent Workbench.'
      : compactStatusDetail(wslOutput || 'AgenticOSClean route did not respond.')

  const statusCards = useMemo(() => [
    {
      name: 'Backend',
      role: 'Dashboard API',
      state: backendState.status === 'loading' ? 'loading' : backendReady ? 'local' : 'error',
      stateLabel: backendState.status === 'loading' ? 'Checking API' : backendReady ? 'Healthy' : 'Offline',
      detail: backendState.status === 'loading'
        ? 'Loading health from /api/health.'
        : backendReady
          ? `API ${backendState.data?.version || 'online'} is responding.`
          : 'Overview data could not be refreshed from the backend.',
      icon: Server,
    },
    {
      name: 'Clean WSL',
      role: 'AgenticOSClean availability',
      state: wslState.status === 'loading' ? 'loading' : wslReady ? 'ready' : 'error',
      stateLabel: wslState.status === 'loading' ? 'Checking WSL' : wslReady ? 'Available' : 'Unavailable',
      detail: wslState.status === 'loading'
        ? 'Checking /api/wsl/status without launching an agent task.'
        : wslReady
          ? 'AgenticOSClean responded through the clean WSL status route.'
          : compactStatusDetail(wslOutput || 'WSL status check failed.'),
      icon: Terminal,
    },
    {
      name: 'Hermes',
      role: 'Coordinator route',
      state: routeState,
      stateLabel: routeLabel,
      detail: routeDetail,
      icon: Sparkles,
    },
    {
      name: 'Codex',
      role: 'Implementation route',
      state: routeState,
      stateLabel: routeLabel,
      detail: routeDetail,
      icon: Code2,
    },
    {
      name: 'Claude',
      role: 'Precision route',
      state: routeState,
      stateLabel: routeLabel,
      detail: routeDetail,
      icon: Bot,
    },
  ], [backendReady, backendState, routeDetail, routeLabel, routeState, wslOutput, wslReady, wslState])

  const agentCards = [
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
          onClick={() => {
            onRefresh?.()
            refreshStatus()
          }}
          className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone"
        >
          <Activity size={13} />
          Refresh overview
        </button>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <div className="sm:col-span-2 lg:col-span-3">
          <TokenStatusCard
            loading={overviewLoading}
            error={overviewError}
            tokenUsage={tokenUsage}
            lastTokenText={lastTokenText}
            lastRoute={lastRoute}
            lastTimestamp={lastTimestamp}
          />
        </div>
        <div className="sm:col-span-2 lg:col-span-2">
          <QueueOverviewCard state={queueState} />
        </div>
        <SummaryCard label="Packets" value={packets} sub="saved locally" icon={FileText} accent="text-champagne" />
        <SummaryCard label="Logs" value={logs} sub="available in logs/results" icon={ScrollText} />
        <SummaryCard label="Results" value={results} sub="completed outputs" icon={FolderOpen} />
        <SummaryCard
          label="Estimated Value"
          value={`$${formatCount(estimatedValue)}`}
          sub="from tracker"
          icon={Gauge}
          accent={estimatedValue > 0 ? 'text-champagne' : 'text-taupe'}
        />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Cockpit Status</h2>
          <ShieldCheck size={14} className="text-taupe" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {statusCards.map(status => <StatusCard key={status.name} {...status} />)}
        </div>
      </section>

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

      <section className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Operator Surfaces</h2>
            <LayoutDashboard size={14} className="text-taupe" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {agentCards.map(agent => <AgentCard key={agent.name} {...agent} />)}
          </div>
        </div>

        <div className="space-y-4 lg:col-span-2">
          <div className="rounded-lg border border-softgraph bg-graphite p-5">
            <div className="mb-1 flex items-center gap-2">
              <Wrench size={14} className="text-taupe" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Quick Links</h2>
            </div>
            <QuickLink label="Logs and results" sub={`${logs} logs, ${results} results`} icon={ScrollText} onClick={() => onNavigate?.('logs')} />
            <QuickLink label="Queue" sub="Review active work items" icon={ListChecks} onClick={() => onNavigate?.('queue')} />
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
