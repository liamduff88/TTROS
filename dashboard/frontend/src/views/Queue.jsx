import { useEffect, useState } from 'react'
import { Activity, AlertCircle, CheckCircle2, Clock, ListChecks, RefreshCw } from 'lucide-react'
import { getQueueSummary } from '../api'

const QUEUE_STATUSES = [
  'inbox',
  'agent_todo',
  'agent_working',
  'needs_input',
  'human_review',
  'done',
  'blocked',
  'cancelled',
]

const NEEDS_LIAM_STATUSES = new Set(['needs_input', 'human_review', 'blocked'])

const formatStatus = value => String(value || '').replace(/_/g, ' ')

const formatTime = value => {
  if (!value) return 'No timestamp'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown time' : date.toLocaleString()
}

const compactReason = value => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return 'Backend queue summary did not return a reason.'
  return text.length > 160 ? `${text.slice(0, 157).trim()}...` : text
}

const QueueItem = ({ item }) => {
  const needsLiam = NEEDS_LIAM_STATUSES.has(item.status)

  return (
    <div className="grid gap-3 border-b border-softgraph py-3 text-xs last:border-0 md:grid-cols-[8.5rem_8rem_5rem_1fr_10rem]">
      <div className="font-mono text-stone">{item.id || 'No ID'}</div>
      <div className={`font-mono ${needsLiam ? 'text-champagne' : 'text-taupe'}`}>{formatStatus(item.status)}</div>
      <div className="font-mono text-taupe">{item.owner || 'unassigned'}</div>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-ivory" title={item.title || ''}>{item.title || 'Untitled queue item'}</div>
        <div className="mt-0.5 font-mono text-taupe">Priority {item.priority ?? 0}</div>
      </div>
      <div className="font-mono text-taupe">{formatTime(item.updated_at || item.created_at)}</div>
    </div>
  )
}

const CountTile = ({ label, value, accent }) => (
  <div className="rounded-lg border border-softgraph bg-graphite p-4">
    <div className="text-xs font-medium uppercase tracking-wider text-taupe">{label}</div>
    <div className={`mt-3 text-2xl font-mono font-semibold ${accent || 'text-stone'}`}>{value ?? 0}</div>
  </div>
)

export default function Queue() {
  const [state, setState] = useState({ status: 'loading', data: null, error: null })

  const refreshQueue = () => {
    setState(current => ({ ...current, status: 'loading', error: null }))
    getQueueSummary()
      .then(data => setState({ status: data?.success ? 'ready' : 'error', data, error: null }))
      .catch(error => setState({ status: 'error', data: null, error }))
  }

  useEffect(() => {
    refreshQueue()
  }, [])

  const loading = state.status === 'loading'
  const error = state.status === 'error'
  const counts = state.data?.counts || {}
  const activeItems = state.data?.activeItems || []
  const activeCount = state.data?.activeCount ?? activeItems.length
  const nextItem = state.data?.nextItem
  const reason = state.data?.reason || state.error?.response?.data?.detail || state.error?.message

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-champagne">Queue</p>
          <h1 className="mt-1 text-2xl font-semibold text-ivory">Agentic OS Work Queue</h1>
          <p className="mt-1 text-sm text-taupe">Read-only view of local queue status, active items, and the next item.</p>
        </div>
        <button
          type="button"
          onClick={refreshQueue}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-clay/40 bg-clay/10 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-stone">
            <AlertCircle size={15} className="text-clay" />
            Queue unavailable
          </div>
          <div className="mt-2 text-xs font-mono text-taupe">{compactReason(reason)}</div>
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <CountTile label="Active Items" value={activeCount} accent="text-champagne" />
        <CountTile label="Needs Liam" value={state.data?.needsLiam ?? 0} accent={(state.data?.needsLiam ?? 0) > 0 ? 'text-champagne' : 'text-taupe'} />
        <CountTile label="Inbox" value={counts.inbox} />
        <CountTile label="Working" value={counts.agent_working} />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-softgraph bg-graphite p-5 lg:col-span-1">
          <div className="mb-3 flex items-center gap-2">
            <CheckCircle2 size={14} className="text-champagne" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Next Item</h2>
          </div>
          {loading ? (
            <div className="rounded border border-softgraph bg-ink px-4 py-6 text-center text-xs font-mono text-taupe">Loading queue.</div>
          ) : nextItem ? (
            <div>
              <div className="font-mono text-xs text-champagne">{nextItem.id}</div>
              <div className="mt-2 text-base font-semibold text-ivory">{nextItem.title || 'Untitled queue item'}</div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <div className="text-taupe">Status</div>
                  <div className="text-stone">{formatStatus(nextItem.status)}</div>
                </div>
                <div>
                  <div className="text-taupe">Owner</div>
                  <div className="text-stone">{nextItem.owner || 'unassigned'}</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded border border-softgraph bg-ink px-4 py-6 text-center text-xs font-mono text-taupe">No active queue items.</div>
          )}
        </div>

        <div className="rounded-lg border border-softgraph bg-graphite p-5 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-taupe" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Status Counts</h2>
            </div>
            <Clock size={14} className="text-taupe" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {QUEUE_STATUSES.map(status => (
              <div key={status} className="rounded border border-softgraph bg-ink px-3 py-3">
                <div className="text-[11px] font-mono uppercase tracking-wider text-taupe">{formatStatus(status)}</div>
                <div className="mt-2 text-lg font-mono text-stone">{counts[status] ?? 0}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-softgraph bg-graphite p-5">
        <div className="mb-3 flex items-center gap-2">
          <ListChecks size={14} className="text-taupe" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Active Items</h2>
        </div>
        {loading ? (
          <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">Loading active items.</div>
        ) : activeItems.length > 0 ? (
          <div className="divide-y divide-softgraph">
            {activeItems.map(item => <QueueItem key={item.id || item.title} item={item} />)}
          </div>
        ) : (
          <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">No active queue items.</div>
        )}
      </section>
    </div>
  )
}
