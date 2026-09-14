import { Bot, Circle, Copy, MoreVertical, Monitor, RefreshCw, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getHermesUiStatus, launchHermesUi } from '../api'
import { launcherPrompt } from '../launcherPrompts'
import { DESTINATIONS } from '../shellState'

// Compact header: current surface + backend/Needs Me status stay always
// visible; every launcher/status utility that used to live in a horizontally
// scrolling row now lives behind the overflow menu (BUILD_SPECIFICATION
// "Replace the current always-wide utility bar with a compact header").
export default function TopBar({ activeDestination, backendOk, cockpit, onNavigate, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)
  const [copied, setCopied] = useState('')
  const [hermesUi, setHermesUi] = useState(null)
  const [hermesUiBusy, setHermesUiBusy] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

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
  const surfaceLabel = DESTINATIONS.find(destination => destination.id === activeDestination)?.label || 'David'

  useEffect(() => {
    getHermesUiStatus().then(setHermesUi).catch(() => setHermesUi({ state: 'configuration_missing' }))
  }, [])

  useEffect(() => {
    if (!menuOpen) return undefined
    const onClickAway = event => { if (menuRef.current && !menuRef.current.contains(event.target)) setMenuOpen(false) }
    const onEscape = event => { if (event.key === 'Escape') setMenuOpen(false) }
    document.addEventListener('mousedown', onClickAway)
    document.addEventListener('keydown', onEscape)
    return () => { document.removeEventListener('mousedown', onClickAway); document.removeEventListener('keydown', onEscape) }
  }, [menuOpen])

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

  const statusColor = blocked ? 'text-clay fill-clay' : needs ? 'text-champagne fill-champagne' : backendOk ? 'text-olive fill-olive' : 'text-taupe fill-taupe'
  const statusText = blocked ? `${blocked} blocked` : needs ? `${needs} needs me` : backendOk ? 'ready' : 'API offline'

  return (
    <header className="relative flex flex-shrink-0 items-center justify-between gap-2 border-b border-softgraph bg-graphite px-3 py-2.5" data-testid="utility-topbar">
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate text-sm font-semibold text-ivory" data-testid="topbar-surface-title">{surfaceLabel}</span>
        <span className="hidden items-center gap-1.5 sm:flex">
          <Circle size={8} className={statusColor} />
          <span className="font-mono text-xs text-taupe" data-testid="topbar-status-text">{statusText}</span>
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <button onClick={() => onNavigate('work-queue', { status: 'human_review' })} className="rounded border border-softgraph bg-ink px-2 py-1.5 font-mono text-[11px] text-champagne sm:hidden" title={statusText}>
          <Circle size={8} className={`inline ${statusColor}`} /> {needs || blocked || 0}
        </button>
        <button onClick={handleRefresh} className="rounded p-1.5 text-taupe transition-colors hover:text-stone" title="Refresh dashboard" aria-label="Refresh dashboard">
          <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
        </button>
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(value => !value)}
            className="rounded p-1.5 text-taupe transition-colors hover:bg-softgraph hover:text-stone"
            aria-label="More utilities"
            aria-expanded={menuOpen}
            data-testid="topbar-overflow-toggle"
          >
            <MoreVertical size={16} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full z-30 mt-1 w-72 max-w-[calc(100vw-1.5rem)] rounded border border-softgraph bg-graphite p-2 shadow-2xl" role="menu" data-testid="topbar-overflow-menu">
              <div className="rounded border border-softgraph bg-ink px-2.5 py-2 text-xs font-mono text-champagne">{tokenChip}</div>
              <button onClick={copyTelegramFallback} className="mt-2 flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-xs text-stone hover:bg-softgraph" title="Copy Telegram instructions; this dashboard does not send messages">
                <Copy size={13} />{copied === 'telegram' ? 'Copied Telegram instructions' : 'Telegram instructions'}
              </button>
              <button
                onClick={openHermesUi}
                disabled={hermesUiBusy || hermesUi?.supported === false}
                className="mt-1 flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-xs text-stone hover:bg-softgraph disabled:opacity-50"
                title={hermesUi?.reason || hermesUi?.launch_command || 'Start or open the local Hermes dashboard at 127.0.0.1:8081'}
              >
                <Monitor size={13} />{hermesUiBusy ? 'Starting Hermes UI' : hermesUi?.http_reachable ? 'Open Hermes UI' : hermesUi?.supported === false ? 'Hermes UI unavailable' : 'Launch Hermes UI'}
              </button>
              <button
                onClick={() => latitude.workspace_url && window.open(latitude.workspace_url, '_blank')}
                disabled={!latitude.workspace_url}
                className="mt-1 flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-xs text-stone hover:bg-softgraph disabled:opacity-50"
                title={latitudeTitle}
              >
                <Bot size={13} />Latitude {latitude.workspace_url ? 'open' : latitudeLabel}
              </button>
              <button onClick={() => copyPrompt('codex')} className="mt-1 flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-xs text-stone hover:bg-softgraph">
                <Copy size={13} />{copied === 'codex' ? 'Copied Codex' : 'Codex copy-prompt'}
              </button>
              <button onClick={() => copyPrompt('claude-code')} className="mt-1 flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-xs text-stone hover:bg-softgraph">
                <Copy size={13} />{copied === 'claude-code' ? 'Copied Claude' : 'Claude Code copy-prompt'}
              </button>
              <button onClick={() => onNavigate('system', { tab: 'tokens' })} className="mt-1 flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-xs text-stone hover:bg-softgraph">
                <Zap size={13} />Open Tokens
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
