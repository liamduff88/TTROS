import { Bot, Circle, Copy, Monitor, RefreshCw, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getHermesUiStatus, launchHermesUi } from '../api'
import { launcherPrompt } from '../launcherPrompts'

export default function TopBar({ backendOk, cockpit, onNavigate, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)
  const [copied, setCopied] = useState('')
  const [query, setQuery] = useState('')
  const [hermesUi, setHermesUi] = useState(null)
  const [hermesUiBusy, setHermesUiBusy] = useState(false)

  const counts = cockpit?.counts || {}
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (cockpit?.stalled?.length || 0)
  const blocked = counts.blocked || 0
  const tokenChip = cockpit?.tokens?.strip?.today?.label || 'Token usage: unavailable from current CLI output'
  const latitude = cockpit?.latitude || {}
  const latitudeLabel = latitude.configured
    ? (latitude.connected === true ? 'connected' : 'configured')
    : 'not configured'
  const latitudeTitle = latitude.workspace_url
    ? 'Open configured Latitude workspace'
    : (latitude.degraded_reason || 'Latitude workspace URL not configured')
  useEffect(() => {
    getHermesUiStatus().then(setHermesUi).catch(() => setHermesUi({ state: 'configuration_missing' }))
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.resolve(onRefresh?.())
    setTimeout(() => setRefreshing(false), 600)
  }

  const copyTelegramFallback = async () => {
    await navigator.clipboard?.writeText('Telegram is instructions-only in this dashboard. Use the existing installed client or the established internal bridge outside this surface; no message is sent here.')
    setCopied('telegram')
    setTimeout(() => setCopied(''), 1400)
  }

  const copyPrompt = async target => {
    await navigator.clipboard?.writeText(launcherPrompt(target))
    setCopied(target)
    setTimeout(() => setCopied(''), 1400)
  }

  const openHermesUi = async () => {
    setHermesUiBusy(true)
    const hermesWindow = window.open('', 'hermes_os')
    try {
      const launchResult = hermesUi?.http_reachable ? hermesUi : await launchHermesUi()
      const status = await getHermesUiStatus().catch(() => launchResult)
      setHermesUi(status)
      if (status?.http_reachable && status?.url) {
        if (hermesWindow) hermesWindow.location = status.url
        else window.open(status.url, 'hermes_os')
      } else {
        hermesWindow?.close()
        setHermesUi({ ...status, reason: status?.message || status?.last_error || 'Hermes UI did not become reachable.' })
      }
    } catch (error) {
      hermesWindow?.close()
      setHermesUi({ state: 'configuration_missing', reason: error?.response?.data?.message || error?.message || 'Dashboard backend could not launch Hermes UI.' })
    } finally {
      setHermesUiBusy(false)
    }
  }

  const submitSearch = event => {
    event.preventDefault()
    const clean = query.trim()
    if (clean) onNavigate('search', { q: clean })
  }

  const now = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  const statusColor = blocked ? 'text-clay fill-clay' : needs ? 'text-champagne fill-champagne' : backendOk ? 'text-olive fill-olive' : 'text-taupe fill-taupe'

  return (
    <header className="flex flex-nowrap items-center gap-2 overflow-x-auto bg-graphite px-3 py-2 border-b border-softgraph flex-shrink-0" data-testid="utility-topbar">
      <div className="flex shrink-0 flex-nowrap items-center gap-1.5">
        <div className="mr-1 hidden items-center gap-1.5 md:flex">
          <Circle size={8} className={statusColor} />
          <span className="text-xs font-mono text-taupe">{blocked ? `${blocked} blocked` : needs ? `${needs} needs me` : backendOk ? 'ready' : 'API offline'}</span>
        </div>
          <button onClick={copyTelegramFallback} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 text-xs text-stone hover:border-champagne/50" title="Copy Telegram instructions; this dashboard does not send messages"><Copy size={13} />{copied === 'telegram' ? 'Copied Telegram instructions' : 'Telegram instructions'}</button>
          <button
            onClick={openHermesUi}
            disabled={hermesUiBusy || hermesUi?.supported === false}
            title={hermesUi?.reason || hermesUi?.launch_command || 'Start or open the local Hermes dashboard at 127.0.0.1:8081'}
            className={`inline-flex h-8 items-center gap-1.5 rounded border px-2.5 text-xs ${
              hermesUi?.http_reachable
                ? 'border-softgraph bg-softgraph/40 text-stone hover:bg-softgraph'
                : hermesUi?.supported === false
                  ? 'border-softgraph bg-ink text-taupe opacity-60'
                  : 'border-softgraph bg-ink text-stone hover:border-champagne/50'
            }`}
          >
            <Monitor size={13} />{hermesUiBusy ? 'Starting Hermes UI' : hermesUi?.http_reachable ? 'Open Hermes UI' : hermesUi?.supported === false ? 'Hermes UI unavailable' : 'Launch Hermes UI'}
          </button>
          <button
            onClick={() => latitude.workspace_url && window.open(latitude.workspace_url, '_blank')}
            disabled={!latitude.workspace_url}
            title={latitudeTitle}
            className={`inline-flex h-8 items-center gap-1.5 rounded border px-2.5 text-xs ${
              latitude.workspace_url ? 'border-softgraph bg-ink text-stone hover:border-champagne/50' : 'border-softgraph bg-ink text-taupe opacity-60'
            }`}
          >
            <Bot size={13} />Latitude {latitude.workspace_url ? 'open' : latitudeLabel}
          </button>
          <button onClick={() => copyPrompt('codex')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 text-xs text-stone hover:border-champagne/50"><Copy size={13} />{copied === 'codex' ? 'Copied Codex' : 'Codex copy-prompt'}</button>
          <button onClick={() => copyPrompt('claude-code')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 text-xs text-stone hover:border-champagne/50"><Copy size={13} />{copied === 'claude-code' ? 'Copied Claude' : 'Claude Code copy-prompt'}</button>
      </div>
        <form onSubmit={submitSearch} className="flex h-8 min-w-48 shrink-0 items-center rounded border border-softgraph bg-ink px-2 text-xs text-stone focus-within:border-champagne/60">
          <Search size={13} className="text-taupe" />
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search local index" className="ml-2 w-44 bg-transparent outline-none placeholder:text-taupe" />
        </form>
        <button onClick={() => onNavigate('tokens-roi')} className="rounded border border-softgraph bg-ink px-2.5 py-1.5 text-xs font-mono text-champagne">{tokenChip}</button>
        <div className="hidden text-xs text-taupe font-mono lg:block">{new Date().toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })} · {now}</div>
        <button onClick={handleRefresh} className="text-taupe hover:text-stone transition-colors" title="Refresh dashboard">
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
        </button>
    </header>
  )
}
