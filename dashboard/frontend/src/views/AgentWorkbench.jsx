import { useState, useEffect } from 'react'
import { Copy, ExternalLink, Check, AlertCircle, Wifi, WifiOff, Clock, Play, Terminal } from 'lucide-react'
import { getEntities, launchEntity, wslStatus, wslHermes, wslClaude, wslCodex , telegramStatus } from '../api'

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
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-mono bg-softgraph text-taupe hover:text-stone disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
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
      className={`w-full text-left p-4 rounded-lg border transition-colors ${
        selected
          ? 'border-champagne bg-softgraph'
          : 'border-softgraph bg-graphite hover:border-taupe'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-sm font-semibold text-ivory">{entity.name}</span>
        <div className={`w-2 h-2 rounded-full mt-1 ${sc.dot}`} />
      </div>
      <div className="text-xs text-taupe mb-2">{entity.role}</div>
      <div className={`text-[10px] font-mono ${sc.color}`}>{sc.label}</div>
    </button>
  )
}

function LaunchButton({ entity, onResult }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

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
        disabled={loading}
        className={`flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-colors ${
          entity.launchable
            ? 'bg-champagne text-ink hover:bg-stone'
            : 'bg-softgraph text-taupe cursor-not-allowed'
        }`}
      >
        <ExternalLink size={13} />
        {loading ? 'Launching…' : entity.launchable ? `Open ${entity.name}` : entity.commandType === 'wsl' ? 'Use Hermes Run Panel' : entity.statusLabel || sc.label}
      </button>
      {result && (
        <div className={`text-xs font-mono px-3 py-1.5 rounded border ${
          result.success
            ? 'border-olive/40 bg-olive/10 text-stone'
            : 'border-clay/40 bg-clay/10 text-stone'
        }`}>
          {result.message}
        </div>
      )}
    </div>
  )
}

function HermesRunPanel() {
  const [task, setTask] = useState('')
  const [running, setRunning] = useState(null) // 'status' | 'hermes' | 'claude' | 'codex'
  const [result, setResult] = useState(null)

  const run = async (action) => {
    setRunning(action)
    setResult(null)
    try {
      let res
      if (action === 'status') res = await wslStatus()
      else if (action === 'hermes') res = await wslHermes(task)
      else if (action === 'claude') res = await wslClaude(task)
      else if (action === 'codex') res = await wslCodex(task)
      setResult(res)
    } catch (e) {
      setResult({ success: false, output: e?.response?.data?.detail || 'Backend unreachable or request failed' })
    } finally {
      setRunning(null)
    }
  }

  const needsTask = (action) => action !== 'status' && !task.trim()

  return (
    <div className="bg-graphite border border-softgraph rounded-lg p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Terminal size={13} className="text-champagne" />
        <span className="text-xs font-semibold text-taupe uppercase tracking-wider">Hermes Run Panel — AgenticOSClean WSL</span>
      </div>

      <div>
        <label className="block text-xs text-taupe mb-1.5 font-medium">Task text (for Hermes → Codex, Hermes → Claude, or Direct Codex)</label>
              <div className="rounded-2xl border border-stone-700/40 bg-black/20 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-stone-400">Telegram Bridge</div>
        <div className="mt-2 text-lg font-semibold text-stone-100">{telegram?.running ? 'Running' : 'Stopped'}</div>
        <div className="mt-1 text-sm text-stone-400">Pilot: northshore_honda_sales_demo</div>
        <div className="mt-1 text-sm text-stone-400">Reports: {telegram?.pilot_report_count ?? 0}</div>
      </div>
<textarea
          value={task}
          onChange={e => setTask(e.target.value)}
          placeholder="Describe the coding task…"
          rows={4}
          className="w-full bg-ink border border-softgraph rounded px-3 py-2 text-sm text-ivory placeholder-taupe/50 font-mono resize-none focus:outline-none focus:border-taupe"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => run('status')}
          disabled={!!running}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-softgraph text-stone hover:text-ivory disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <Play size={11} />
          {running === 'status' ? 'Checking…' : 'Hermes Status'}
        </button>
        <button
          onClick={() => run('hermes')}
          disabled={!!running || needsTask('hermes')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-champagne text-ink hover:bg-stone disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={needsTask('hermes') ? 'Enter task text first' : ''}
        >
          <Play size={11} />
          {running === 'hermes' ? 'Running…' : 'Hermes → Codex'}
        </button>
        <button
          onClick={() => run('claude')}
          disabled={!!running || needsTask('claude')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-softgraph text-stone hover:text-ivory disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={needsTask('claude') ? 'Enter task text first' : ''}
        >
          <Play size={11} />
          {running === 'claude' ? 'Running…' : 'Hermes → Claude'}
        </button>
        <button
          onClick={() => run('codex')}
          disabled={!!running || needsTask('codex')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-softgraph text-stone hover:text-ivory disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title={needsTask('codex') ? 'Enter task text first' : ''}
        >
          <Play size={11} />
          {running === 'codex' ? 'Running…' : 'Direct Codex'}
        </button>
      </div>

      {running && (
        <div className="text-xs font-mono text-taupe animate-pulse px-1">Running inside AgenticOSClean — may take up to 2 min…</div>
      )}

      {result && (
        <div className={`rounded border px-4 py-3 text-xs font-mono whitespace-pre-wrap leading-relaxed ${
          result.success
            ? 'border-olive/40 bg-olive/10 text-stone'
            : 'border-clay/40 bg-clay/10 text-stone'
        }`}>
          <div className={`text-[10px] uppercase tracking-wider mb-1 ${result.success ? 'text-olive' : 'text-clay'}`}>
            {result.success ? 'Success' : 'Error'}
          </div>
          {result.output}
        </div>
      )}
    </div>
  )
}

export default function AgentWorkbench() {
  const [telegram, setTelegram] = useState(null);
  useEffect(() => { telegramStatus().then(setTelegram).catch(() => setTelegram({ status: 'offline', running: false })); }, []);
  const [entities, setEntities] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEntities()
      .then(d => {
        setEntities(d.entities)
        setSelected(d.entities[0] || null)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-taupe text-sm font-mono">Loading agents…</div>

  const sc = selected ? STATUS_CONFIG[selected.status] || STATUS_CONFIG.not_connected : null

  return (
    <div className="flex gap-6 max-w-5xl">
      <div className="w-56 flex-shrink-0 space-y-2">
        <h2 className="text-xs font-semibold text-taupe uppercase tracking-wider mb-3">Workbench</h2>
        {entities.map(e => (
          <AgentCard
            key={e.id}
            entity={e}
            selected={selected?.id === e.id}
            onSelect={setSelected}
          />
        ))}
      </div>

      {selected && (
        <div className="flex-1 space-y-4">
          <div className="bg-graphite border border-softgraph rounded-lg p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h1 className="text-xl font-semibold text-ivory mb-1">{selected.name}</h1>
                <p className="text-sm text-taupe">{selected.role}</p>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-softgraph">
                <div className={`w-2 h-2 rounded-full ${sc.dot}`} />
                <span className={`text-xs font-mono ${sc.color}`}>{sc.label}</span>
              </div>
            </div>

            <p className="text-sm text-stone leading-relaxed mb-5">{selected.description}</p>

            <div className="flex flex-wrap gap-2 mb-5">
              {selected.capabilities.map(cap => (
                <span key={cap} className="px-2.5 py-1 rounded bg-softgraph text-xs text-stone border border-softgraph">
                  {cap}
                </span>
              ))}
            </div>

            <LaunchButton entity={selected} />
          </div>

          {selected.command && (
            <div className="bg-graphite border border-softgraph rounded-lg p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-taupe uppercase tracking-wider">Command / Path</span>
                <CopyButton text={selected.command} />
              </div>
              <div className="bg-ink rounded px-4 py-3 font-mono text-sm text-stone border border-softgraph">
                {selected.command}
              </div>
              <p className="text-xs text-taupe mt-2">{selected.commandHint}</p>
            </div>
          )}

          {selected.id !== 'hermes' && (
            <div className="bg-graphite border border-softgraph rounded-lg p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertCircle size={13} className="text-taupe" />
                <span className="text-xs font-semibold text-taupe uppercase tracking-wider">v0.1 Notice</span>
              </div>
              <p className="text-xs text-taupe leading-relaxed">
                Agent cards are local operator surfaces. Live execution is available through the Hermes Run Panel inside AgenticOSClean for Codex and Claude. Normal navigation remains zero-token.
              </p>
            </div>
          )}

          {selected.id === 'hermes' && <HermesRunPanel />}
        </div>
      )}
    </div>
  )
}


