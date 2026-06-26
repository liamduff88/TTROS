import { useState, useEffect } from 'react'
import {
  AlertCircle,
  Check,
  ClipboardList,
  Code2,
  Copy,
  ExternalLink,
  Play,
  RefreshCw,
  Route,
  Sparkles,
  Terminal,
} from 'lucide-react'
import { getEntities, launchEntity, wslStatus, wslHermes, wslClaude, wslCodex } from '../api'

const STATUS_CONFIG = {
  live_wsl: { color: 'text-champagne', dot: 'bg-champagne', label: 'Live via AgenticOSClean' },
  live_router: { color: 'text-champagne', dot: 'bg-champagne', label: 'Live router via AgenticOSClean' },
  windows_operator: { color: 'text-olive', dot: 'bg-olive', label: 'Windows dashboard builder/operator UI' },
  browser_only: { color: 'text-olive', dot: 'bg-olive', label: 'Browser/operator strategy' },
  local_live: { color: 'text-olive', dot: 'bg-olive', label: 'Agentic OS Live only' },
  archive_only: { color: 'text-taupe', dot: 'bg-taupe', label: 'Archive only' },
  not_connected: { color: 'text-taupe', dot: 'bg-taupe', label: 'Not Connected' },
  setup_pending: { color: 'text-taupe', dot: 'bg-taupe', label: 'Setup Pending' },
  placeholder: { color: 'text-taupe', dot: 'bg-taupe', label: 'Coming Soon' },
  installed: { color: 'text-champagne', dot: 'bg-champagne', label: 'Installed' },
}

const LAUNCH_CHOICES = [
  {
    id: 'hermes',
    label: 'Hermes',
    routeLabel: 'Coordinator route',
    buttonLabel: 'Route with Hermes',
    icon: Route,
    description: 'Use Hermes for routing, coordinator decisions, multi-step delegation, and tasks where the right agent is not obvious.',
  },
  {
    id: 'codex',
    label: 'Codex',
    routeLabel: 'Implementation route',
    buttonLabel: 'Launch Codex',
    icon: Code2,
    description: 'Use Codex for code and file implementation, focused fixes, tests, docs, and repo-local execution.',
  },
  {
    id: 'claude',
    label: 'Claude',
    routeLabel: 'Precision route',
    buttonLabel: 'Launch Claude',
    icon: Sparkles,
    description: 'Use Claude for careful refactors, UI polish, review passes, and precision edits where taste and structure matter.',
  },
]

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    if (!text) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button
      onClick={handleCopy}
      disabled={!text}
      className="flex items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 py-1.5 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-30"
      title="Copy to clipboard"
    >
      {copied ? <Check size={11} className="text-olive" /> : <Copy size={11} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function AgentCard({ entity, selected, onSelect }) {
  const sc = STATUS_CONFIG[entity.status] || STATUS_CONFIG.not_connected
  return (
    <button
      onClick={() => onSelect(entity)}
      className={`w-full rounded-lg border p-4 text-left transition-colors ${
        selected
          ? 'border-champagne bg-softgraph'
          : 'border-softgraph bg-graphite hover:border-taupe'
      }`}
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <span className="text-sm font-semibold text-ivory">{entity.name}</span>
        <div className={`mt-1 h-2 w-2 rounded-full ${sc.dot}`} />
      </div>
      <div className="mb-2 text-xs text-taupe">{entity.role}</div>
      <div className={`text-[10px] font-mono ${sc.color}`}>{sc.label}</div>
    </button>
  )
}

function LaunchButton({ entity }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const sc = STATUS_CONFIG[entity.status] || STATUS_CONFIG.not_connected

  const handle = async () => {
    setLoading(true)
    try {
      const r = await launchEntity(entity.id)
      setResult(r)
    } catch {
      setResult({ success: false, message: 'Backend unreachable' })
    } finally {
      setLoading(false)
      setTimeout(() => setResult(null), 4000)
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handle}
        disabled={loading || !entity.launchable}
        className={`flex items-center gap-2 rounded px-4 py-2 text-sm font-medium transition-colors ${
          entity.launchable
            ? 'bg-champagne text-ink hover:bg-stone'
            : 'cursor-not-allowed bg-softgraph text-taupe'
        }`}
      >
        <ExternalLink size={13} />
        {loading ? 'Opening...' : entity.launchable ? `Open ${entity.name}` : entity.commandType === 'wsl' ? 'Use command bar' : entity.statusLabel || sc.label}
      </button>
      {result && (
        <div className={`rounded border px-3 py-1.5 text-xs font-mono ${
          result.success
            ? 'border-olive/40 bg-olive/10 text-stone'
            : 'border-clay/40 bg-clay/10 text-stone'
        }`}
        >
          {result.message}
        </div>
      )}
    </div>
  )
}

function AgentRouteChoice({ choice, active, onSelect }) {
  const Icon = choice.icon
  return (
    <button
      onClick={() => onSelect(choice.id)}
      className={`min-h-[138px] rounded-lg border p-4 text-left transition-colors ${
        active
          ? 'border-champagne bg-softgraph'
          : 'border-softgraph bg-ink/60 hover:border-taupe'
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`flex h-8 w-8 items-center justify-center rounded border ${
            active ? 'border-champagne text-champagne' : 'border-softgraph text-taupe'
          }`}
          >
            <Icon size={16} />
          </span>
          <div>
            <div className="text-sm font-semibold text-ivory">{choice.label}</div>
            <div className="text-[10px] uppercase tracking-wider text-taupe">{choice.routeLabel}</div>
          </div>
        </div>
        {active && <Check size={15} className="text-champagne" />}
      </div>
      <p className="text-xs leading-relaxed text-stone">{choice.description}</p>
    </button>
  )
}

function CommandBar() {
  const [task, setTask] = useState('')
  const [route, setRoute] = useState('hermes')
  const [running, setRunning] = useState(null)
  const [result, setResult] = useState(null)

  const selectedChoice = LAUNCH_CHOICES.find(choice => choice.id === route) || LAUNCH_CHOICES[0]
  const canLaunch = task.trim().length > 0 && !running

  const run = async (action) => {
    setRunning(action)
    setResult(null)
    try {
      let res
      if (action === 'status') res = await wslStatus()
      else if (action === 'hermes') res = await wslHermes(task)
      else if (action === 'claude') res = await wslClaude(task)
      else if (action === 'codex') res = await wslCodex(task)
      setResult({
        action,
        routeLabel: action === 'status' ? 'Hermes status' : selectedChoice.label,
        task: action === 'status' ? 'Status check' : task.trim(),
        ...res,
      })
    } catch (e) {
      setResult({
        action,
        success: false,
        routeLabel: action === 'status' ? 'Hermes status' : selectedChoice.label,
        task: action === 'status' ? 'Status check' : task.trim(),
        output: e?.response?.data?.detail || 'Backend unreachable or request failed',
      })
    } finally {
      setRunning(null)
    }
  }

  return (
    <section className="rounded-lg border border-softgraph bg-graphite p-5 shadow-2xl shadow-black/20">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Terminal size={14} className="text-champagne" />
            <span className="text-xs font-semibold uppercase tracking-wider text-taupe">AgentWorkbench Command Bar</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-normal text-ivory">Route operator work from the cockpit.</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-taupe">
            Describe the task in normal language, choose the right agent surface, and launch inside AgenticOSClean WSL.
          </p>
        </div>
        <button
          onClick={() => run('status')}
          disabled={!!running}
          className="flex items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 text-xs font-medium text-stone transition-colors hover:border-taupe hover:text-ivory disabled:cursor-not-allowed disabled:opacity-40"
        >
          <RefreshCw size={13} className={running === 'status' ? 'animate-spin' : ''} />
          {running === 'status' ? 'Checking' : 'Hermes Status'}
        </button>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {LAUNCH_CHOICES.map(choice => (
          <AgentRouteChoice
            key={choice.id}
            choice={choice}
            active={route === choice.id}
            onSelect={setRoute}
          />
        ))}
      </div>

      <div className="mt-5 rounded-lg border border-softgraph bg-ink p-4">
        <label className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-taupe">
          <ClipboardList size={13} />
          Natural-language task
        </label>
        <textarea
          value={task}
          onChange={e => setTask(e.target.value)}
          placeholder="Example: Review the dashboard command bar, tighten the UI, run focused validation, and return a compact closeout."
          rows={4}
          className="min-h-[116px] w-full resize-none rounded border border-softgraph bg-black/20 px-3 py-3 text-sm leading-relaxed text-ivory placeholder-taupe/50 focus:border-champagne focus:outline-none"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-taupe">
            Selected: <span className="font-medium text-stone">{selectedChoice.label}</span> through clean AgenticOSClean routes.
          </div>
          <button
            onClick={() => run(route)}
            disabled={!canLaunch}
            className="flex items-center gap-2 rounded bg-champagne px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-stone disabled:cursor-not-allowed disabled:opacity-40"
            title={!task.trim() ? 'Enter a task first' : ''}
          >
            <Play size={14} />
            {running && running !== 'status' ? 'Launching...' : selectedChoice.buttonLabel}
          </button>
        </div>
      </div>

      {(running || result) && (
        <div className="mt-5 rounded-lg border border-softgraph bg-ink">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-softgraph px-4 py-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-taupe">Task status</div>
              <div className="mt-1 text-sm text-stone">
                {running ? 'Running inside AgenticOSClean WSL' : `${result?.routeLabel || 'Agent'} complete`}
              </div>
            </div>
            <div className={`rounded-full px-3 py-1 text-[11px] font-mono ${
              running
                ? 'bg-softgraph text-taupe'
                : result?.success
                  ? 'bg-olive/20 text-stone'
                  : 'bg-clay/20 text-stone'
            }`}
            >
              {running ? 'IN PROGRESS' : result?.success ? 'PASS' : 'NEEDS ATTENTION'}
            </div>
          </div>
          <div className="px-4 py-3">
            {result?.task && (
              <div className="mb-3 line-clamp-2 text-xs text-taupe">
                Task: <span className="text-stone">{result.task}</span>
              </div>
            )}
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded border border-softgraph bg-black/20 p-3 text-xs leading-relaxed text-stone">
              {running ? 'Waiting for compact closeout from AgenticOSClean...' : result?.output || result?.message || '(no output)'}
            </pre>
          </div>
        </div>
      )}
    </section>
  )
}

export default function AgentWorkbench() {
  const [entities, setEntities] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEntities()
      .then(d => {
        setEntities(d.entities)
        setSelected(d.entities.find(entity => entity.id === 'hermes') || d.entities[0] || null)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-sm font-mono text-taupe">Loading agents...</div>

  const sc = selected ? STATUS_CONFIG[selected.status] || STATUS_CONFIG.not_connected : null

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <CommandBar />

      <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-2">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-taupe">Operator Surfaces</h2>
          {entities.map(e => (
            <AgentCard
              key={e.id}
              entity={e}
              selected={selected?.id === e.id}
              onSelect={setSelected}
            />
          ))}
        </aside>

        {selected && (
          <div className="space-y-4">
            <section className="rounded-lg border border-softgraph bg-graphite p-5">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="mb-1 text-xl font-semibold text-ivory">{selected.name}</h2>
                  <p className="text-sm text-taupe">{selected.role}</p>
                </div>
                <div className="flex items-center gap-2 rounded-full bg-softgraph px-3 py-1.5">
                  <div className={`h-2 w-2 rounded-full ${sc.dot}`} />
                  <span className={`text-xs font-mono ${sc.color}`}>{sc.label}</span>
                </div>
              </div>

              <p className="mb-5 text-sm leading-relaxed text-stone">{selected.description}</p>

              <div className="mb-5 flex flex-wrap gap-2">
                {selected.capabilities.map(cap => (
                  <span key={cap} className="rounded border border-softgraph bg-ink px-2.5 py-1 text-xs text-stone">
                    {cap}
                  </span>
                ))}
              </div>

              <LaunchButton entity={selected} />
            </section>

            {selected.command && (
              <section className="rounded-lg border border-softgraph bg-graphite p-5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-taupe">Fallback command or path</span>
                  <CopyButton text={selected.command} />
                </div>
                <div className="rounded border border-softgraph bg-ink px-4 py-3 font-mono text-sm text-stone">
                  {selected.command}
                </div>
                <p className="mt-2 text-xs leading-relaxed text-taupe">
                  {selected.commandHint}. Use this only when the cockpit command bar is not the right surface.
                </p>
              </section>
            )}

            <section className="rounded-lg border border-softgraph bg-graphite p-5">
              <div className="mb-3 flex items-center gap-2">
                <AlertCircle size={13} className="text-taupe" />
                <span className="text-xs font-semibold uppercase tracking-wider text-taupe">Runtime boundary</span>
              </div>
              <p className="text-xs leading-relaxed text-taupe">
                Agent execution on this page is limited to existing clean WSL AgenticOSClean routes. Browser and folder launchers stay local; live connector calls are not part of this workbench flow.
              </p>
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
