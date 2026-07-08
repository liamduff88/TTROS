import { Circle, Plus, RefreshCw, Search, Zap } from 'lucide-react'
import { useState } from 'react'
import { createDashboardTask } from '../api'

export default function TopBar({ backendOk, cockpit, onNavigate, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false)
  const [query, setQuery] = useState('')

  const counts = cockpit?.counts || {}
  const needs = (counts.human_review || 0) + (counts.needs_input || 0)
  const blocked = counts.blocked || 0
  const today = cockpit?.tokens?.periods?.today
  const tokenChip = today?.known ? `$${Number(today.cost || 0).toFixed(2)}` : 'unavailable'

  const handleRefresh = async () => {
    setRefreshing(true)
    await Promise.resolve(onRefresh?.())
    setTimeout(() => setRefreshing(false), 600)
  }

  const queueHermes = async () => {
    await createDashboardTask({
      title: 'Ask Hermes from dashboard',
      owner: 'hermes',
      tags: 'dashboard,hermes',
      context: query.trim() || 'Dashboard command bar Hermes question.',
      definition_of_done: 'Hermes response is returned as a receipt with token usage block.',
    })
    onNavigate('work-queue', { workbench: 'hermes' })
  }

  const now = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  const statusColor = blocked ? 'text-clay fill-clay' : needs ? 'text-champagne fill-champagne' : backendOk ? 'text-olive fill-olive' : 'text-taupe fill-taupe'

  return (
    <header className="flex items-center justify-between gap-4 px-5 py-3 bg-graphite border-b border-softgraph flex-shrink-0">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button onClick={() => onNavigate('work-queue')} className="inline-flex h-8 items-center gap-1.5 rounded border border-softgraph bg-softgraph/40 px-3 text-xs font-semibold text-stone hover:bg-softgraph">
          <Plus size={13} />Create task
        </button>
        <button onClick={queueHermes} className="inline-flex h-8 items-center gap-1.5 rounded border border-champagne/60 bg-champagne/10 px-3 text-xs font-semibold text-champagne hover:bg-champagne/20">
          <Zap size={13} />Ask Hermes
        </button>
        <div className="flex h-8 min-w-0 max-w-xl flex-1 items-center gap-2 rounded border border-softgraph bg-ink px-3">
          <Search size={13} className="text-taupe" />
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search everything" className="min-w-0 flex-1 bg-transparent text-xs text-stone outline-none placeholder:text-taupe" />
        </div>
      </div>

      <div className="flex items-center gap-5">
        <div className="hidden items-center gap-1.5 md:flex">
          <Circle size={8} className={statusColor} />
          <span className="text-xs font-mono text-taupe">{blocked ? `${blocked} blocked` : needs ? `${needs} needs me` : backendOk ? 'ready' : 'API offline'}</span>
        </div>
        <button onClick={() => onNavigate('tokens-roi')} className="rounded border border-softgraph bg-ink px-2.5 py-1.5 text-xs font-mono text-champagne">Today {tokenChip}</button>
        <div className="hidden text-xs text-taupe font-mono lg:block">{new Date().toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })} · {now}</div>
        <button onClick={handleRefresh} className="text-taupe hover:text-stone transition-colors" title="Refresh dashboard">
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>
    </header>
  )
}
