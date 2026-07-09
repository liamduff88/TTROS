import { Bot, Circle, Copy, ExternalLink, MessageSquare, Monitor, RefreshCw, Search } from 'lucide-react'
import { useState } from 'react'

export default function TopBar({ backendOk, cockpit, onNavigate, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)
  const [copied, setCopied] = useState('')
  const [query, setQuery] = useState('')

  const counts = cockpit?.counts || {}
  const needs = (counts.human_review || 0) + (counts.needs_input || 0) + (cockpit?.stalled?.length || 0)
  const blocked = counts.blocked || 0
  const tokenChip = cockpit?.tokens?.strip?.today?.label || 'Token usage: unavailable from current CLI output'
  const latitude = cockpit?.latitude || {}
  const tabs = [
    ['message-board', 'Message Board'],
    ['cockpit', 'Cockpit'],
    ['work-queue', 'Queue'],
    ['agents', 'Agents'],
    ['artifacts', 'Artifacts'],
    ['mission-control', 'Mission Control'],
  ]

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.resolve(onRefresh?.())
    setTimeout(() => setRefreshing(false), 600)
  }

  const copyPrompt = async target => {
    const prompt = `Open Agentic OS Live and work only from the active queue item assigned to ${target}. Preserve receipts, token usage lines, and local-only boundaries.`
    await navigator.clipboard?.writeText(prompt)
    setCopied(target)
    setTimeout(() => setCopied(''), 1400)
  }

  const submitSearch = event => {
    event.preventDefault()
    const clean = query.trim()
    if (clean) onNavigate('search', { q: clean })
  }

  const now = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  const statusColor = blocked ? 'text-clay fill-clay' : needs ? 'text-champagne fill-champagne' : backendOk ? 'text-olive fill-olive' : 'text-taupe fill-taupe'

  return (
    <header className="flex flex-col gap-2 bg-graphite px-4 py-3 border-b border-softgraph flex-shrink-0">
      <div className="flex min-w-0 items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          {tabs.map(([id, label]) => (
            <button key={id} onClick={() => onNavigate(id)} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 text-xs font-semibold text-stone hover:border-champagne/50">
              {id === 'message-board' && <MessageSquare size={13} />}
              {label}
            </button>
          ))}
        </div>
        <div className="hidden items-center gap-1.5 md:flex">
          <Circle size={8} className={statusColor} />
          <span className="text-xs font-mono text-taupe">{blocked ? `${blocked} blocked` : needs ? `${needs} needs me` : backendOk ? 'ready' : 'API offline'}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          <button onClick={() => window.open('https://t.me/', '_blank')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-softgraph/40 px-2.5 text-xs text-stone hover:bg-softgraph"><ExternalLink size={13} />Open Telegram</button>
          <button onClick={() => window.open('http://127.0.0.1:3010', '_blank')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-softgraph/40 px-2.5 text-xs text-stone hover:bg-softgraph"><Monitor size={13} />Open Hermes Desktop</button>
          <button
            onClick={() => latitude.workspace_url && window.open(latitude.workspace_url, '_blank')}
            disabled={!latitude.workspace_url}
            title={latitude.workspace_url ? latitude.reason || 'Latitude workspace URL configured at runtime' : 'Latitude workspace URL not configured'}
            className={`inline-flex h-8 items-center gap-1.5 rounded border px-2.5 text-xs ${
              latitude.workspace_url ? 'border-softgraph bg-ink text-stone hover:border-champagne/50' : 'border-softgraph bg-ink text-taupe opacity-60'
            }`}
          >
            <Bot size={13} />Latitude {latitude.workspace_url ? (latitude.status && latitude.status !== 'configured' ? latitude.status : 'open') : 'workspace URL not configured'}
          </button>
          <button onClick={() => copyPrompt('codex')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 text-xs text-stone hover:border-champagne/50"><Copy size={13} />{copied === 'codex' ? 'Copied Codex' : 'Codex copy-prompt'}</button>
          <button onClick={() => copyPrompt('claude-code')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-ink px-2.5 text-xs text-stone hover:border-champagne/50"><Copy size={13} />{copied === 'claude-code' ? 'Copied Claude' : 'Claude Code copy-prompt'}</button>
        </div>
        <form onSubmit={submitSearch} className="flex h-8 min-w-56 items-center rounded border border-softgraph bg-ink px-2 text-xs text-stone focus-within:border-champagne/60">
          <Search size={13} className="text-taupe" />
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search local index" className="ml-2 w-44 bg-transparent outline-none placeholder:text-taupe" />
        </form>
        <button onClick={() => onNavigate('tokens-roi')} className="rounded border border-softgraph bg-ink px-2.5 py-1.5 text-xs font-mono text-champagne">{tokenChip}</button>
        <div className="hidden text-xs text-taupe font-mono lg:block">{new Date().toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })} · {now}</div>
        <button onClick={handleRefresh} className="text-taupe hover:text-stone transition-colors" title="Refresh dashboard">
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>
    </header>
  )
}
