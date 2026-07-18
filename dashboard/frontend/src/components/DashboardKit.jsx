import { useEffect, useState } from 'react'
import { X, Zap, LockKeyhole, ChevronLeft, ChevronRight } from 'lucide-react'
import { workbenchColor } from '../shellState'

export const STATUS_LABELS = {
  inbox: 'Ready',
  agent_todo: 'Ready',
  agent_working: 'Running',
  needs_input: 'Needs Me',
  human_review: 'Needs Me',
  blocked: 'Blocked',
  done: 'Done',
  cancelled: 'Done',
  Ready: 'Ready',
  Running: 'Running',
  'Needs Me': 'Needs Me',
  Blocked: 'Blocked',
  Done: 'Done',
  Unavailable: 'Unavailable',
}

const tone = {
  Ready: 'border-olive/50 bg-olive/15 text-stone',
  Running: 'border-bluegray/60 bg-bluegray/20 text-stone',
  'Needs Me': 'border-champagne/70 bg-champagne/15 text-champagne',
  Blocked: 'border-clay/70 bg-clay/15 text-clay',
  Done: 'border-softgraph bg-softgraph/60 text-taupe',
  Unavailable: 'border-softgraph bg-ink text-taupe',
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || STATUS_LABELS[String(status || '').trim()] || 'Unavailable'
}

export function StatusChip({ status, children }) {
  const toneLabel = statusLabel(status)
  const label = children || toneLabel
  return <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-semibold ${tone[toneLabel] || tone.Unavailable}`}>{label}</span>
}

export function SourceChip({ source }) {
  const value = String(source || 'dashboard').toLowerCase()
  if (value === 'telegram') return <span className="rounded border border-champagne/60 bg-champagne/10 px-1.5 py-0.5 text-[10px] font-bold text-champagne">TG</span>
  return <span className="rounded border border-softgraph bg-softgraph/40 px-1.5 py-0.5 text-[10px] text-taupe">{value}</span>
}

export function ActionButton({ kind = 'neutral', children, className = '', type = 'button', ...props }) {
  const styles = {
    neutral: 'border-softgraph bg-softgraph/40 text-stone hover:bg-softgraph',
    token: 'border-champagne/60 bg-champagne/10 text-champagne hover:bg-champagne/20',
    locked: 'border-clay/60 bg-clay/10 text-clay hover:bg-clay/20',
    primary: 'border-champagne/80 bg-champagne text-ivory hover:bg-well',
  }
  return (
    <button {...props} type={type} className={`inline-flex h-8 items-center justify-center gap-1.5 rounded border px-3 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles[kind]} ${className}`}>
      {kind === 'token' && <Zap size={13} />}
      {kind === 'locked' && <LockKeyhole size={13} />}
      {children}
    </button>
  )
}

export function PageHeader({ title, question, actions }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-ivory">{title}</h1>
        {question && <p className="mt-1 text-sm text-taupe">{question}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function FilterBar({ filters, onChange, text = true }) {
  const set = (key, value) => onChange({ ...filters, [key]: value })
  return (
    <div className="mb-4 grid gap-2 rounded border border-softgraph bg-graphite/60 p-3 md:grid-cols-5">
      {['lane', 'workbench', 'status', 'source'].map(key => (
        <select key={key} value={filters[key] || ''} onChange={event => set(key, event.target.value)} className="h-9 rounded border border-softgraph bg-ink px-2 text-xs text-stone">
          <option value="">{key}</option>
          {(key === 'lane' ? ['revenue', 'marketing', 'delivery', 'operations', 'ops', 'unassigned'] : key === 'status' ? ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'blocked', 'done'] : key === 'source' ? ['dashboard', 'telegram', 'ChatGPT'] : ['hermes', 'codex', 'claude', 'revenue', 'marketing', 'delivery', 'operations']).map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      ))}
      {text && <input value={filters.q || ''} onChange={event => set('q', event.target.value)} placeholder="Search" className="h-9 rounded border border-softgraph bg-ink px-2 text-xs text-stone placeholder:text-taupe" />}
    </div>
  )
}

export function DetailPanel({ item, title, subtitle, onClose, children }) {
  if (!item) return null
  return (
    <div className="fixed inset-y-0 right-0 z-30 w-full max-w-xl border-l border-softgraph bg-graphite shadow-2xl">
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-3 border-b border-softgraph p-4">
          <div>
            <div className="text-xs font-mono text-champagne">{subtitle}</div>
            <h2 className="mt-1 text-lg font-semibold text-ivory">{title}</h2>
          </div>
          <button onClick={onClose} className="rounded p-1 text-taupe hover:bg-softgraph hover:text-stone" title="Close detail"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  )
}

export function EmptyState({ title = 'Unavailable', detail = 'No local data is available yet.', action }) {
  return (
    <div className="rounded border border-softgraph bg-graphite/50 p-6 text-sm text-taupe">
      <div className="text-base font-semibold text-stone">{title}</div>
      <div className="mt-1">{detail}</div>
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function StatTile({ label, value, sub, onClick }) {
  return (
    <button onClick={onClick} className="min-h-24 rounded border border-softgraph bg-graphite/70 p-4 text-left hover:border-champagne/40">
      <div className="text-xs uppercase tracking-wide text-taupe">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-ivory">{value}</div>
      {sub && <div className="mt-1 text-xs text-taupe">{sub}</div>}
    </button>
  )
}

export function RowButton({ title, meta, right, onClick, children }) {
  return (
    <button onClick={onClick} className="group w-full rounded border border-softgraph bg-graphite/50 p-3 text-left hover:border-champagne/40">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-stone">{title}</div>
          {meta && <div className="mt-1 truncate text-xs text-taupe">{meta}</div>}
          {children}
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs text-taupe">{right}<ChevronRight size={14} className="opacity-60 group-hover:text-champagne" /></div>
      </div>
    </button>
  )
}

export function TokenRail({ tokens, onNavigate }) {
  const today = tokens?.periods?.today
  const tools = Array.isArray(tokens?.by_tool) ? tokens.by_tool : []
  const total = today?.known ? `${Number(today.tokens || 0).toLocaleString()} tokens` : 'unavailable'
  return (
    <aside className="hidden min-h-0 w-64 shrink-0 overflow-y-auto border-l border-softgraph bg-graphite/80 p-4 xl:block">
      <div className="text-xs font-mono text-champagne">TODAY</div>
      <div className="mt-2 text-xl font-semibold text-ivory">{total}</div>
      <div className="mt-1 text-xs text-taupe">{today?.known ? `$${Number(today.cost || 0).toFixed(2)} est.` : 'Token usage: unavailable'}</div>
      <div className="mt-5 space-y-3">
        {tools.slice(0, 6).map(tool => (
          <div key={tool.tool}>
            <div className="flex justify-between text-xs">
              <span className="text-stone">{tool.tool}</span>
              <span className="text-taupe">{tool.tokens ? Number(tool.tokens).toLocaleString() : 'unavailable'}</span>
            </div>
            <div className="mt-1 h-1.5 rounded bg-ink">
              {typeof tool.tokens === 'number' && tool.tokens > 0 && (
                <div className="h-1.5 rounded bg-champagne" style={{ width: `${Math.min(100, Math.max(8, (tool.tokens / Math.max(1, tools[0]?.tokens || 1)) * 100))}%` }} />
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded border border-softgraph bg-ink p-3 text-xs text-taupe">
        <div className="text-stone">Highest-cost task</div>
        <div className="mt-1">{tokens?.highest_task?.item_id || 'unavailable'}</div>
      </div>
      <button onClick={() => onNavigate('tokens-roi')} className="mt-4 text-xs font-semibold text-champagne hover:text-stone">Open Tokens & ROI</button>
    </aside>
  )
}

export function NeedsMeRail({ cockpit, onNavigate, collapseKey = null }) {
  const [collapsed, setCollapsed] = useState(false)
  const items = cockpit?.needs_me || []
  const itemCount = items.length
  const strip = cockpit?.tokens?.strip || {}
  const backup = cockpit?.backup || {}
  const backupAttention = backup?.needs_attention
  useEffect(() => {
    if (collapseKey) setCollapsed(true)
  }, [collapseKey])
  if (collapsed) {
    return (
      <aside className="flex w-11 shrink-0 border-l border-softgraph bg-graphite/80" data-testid="needs-me-rail" data-collapsed="true">
        <button onClick={() => setCollapsed(false)} className="flex h-full w-full flex-col items-center gap-2 py-4 text-[var(--needs-review-text)] hover:bg-well" aria-label={`Open Needs Me, ${itemCount} active`}>
          <ChevronLeft size={14} />
          <span className="rounded bg-[var(--needs-review)] px-1.5 py-1 text-xs font-bold" data-testid="needs-me-count">{itemCount}</span>
          <span className="mt-1 [writing-mode:vertical-rl] text-[10px] font-bold uppercase tracking-widest">Needs Me</span>
        </button>
      </aside>
    )
  }
  return (
    <aside className="min-h-0 w-56 shrink-0 overflow-y-auto border-l border-softgraph bg-graphite/80 p-3 xl:w-64" data-testid="needs-me-rail" data-collapsed="false">
      <div className="flex items-center justify-between gap-2">
        <div><div className="text-xs font-mono text-[var(--needs-review-text)]">NEEDS ME</div><div className="mt-1 text-lg font-semibold text-ivory" data-testid="needs-me-count">{itemCount} active</div></div>
        <button onClick={() => setCollapsed(true)} className="rounded p-1.5 text-taupe hover:bg-well hover:text-stone" aria-label="Collapse Needs Me"><ChevronRight size={14} /></button>
      </div>
      <div className="mt-4 space-y-2">
        {items.map(item => (
          <button key={item.id} onClick={() => onNavigate('work-queue', { q: item.id, selectedId: item.id })} className="w-full rounded border bg-ink p-2 text-left" style={{ borderColor: workbenchColor(item.invocation_source, item.status) }} data-needs-me-id={item.id} data-invocation-source={item.invocation_source || 'unattributed'}>
            <div className="truncate text-xs font-semibold text-stone">{item.title}</div>
            <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-taupe">
              <span>{item.id}</span>
              <StatusChip status={item.honest_status || item.status}>{item.stalled_minutes ? 'stalled' : item.status}</StatusChip>
            </div>
            {Array.isArray(item.needs_me) && item.needs_me.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {item.needs_me.map(reason => <span key={reason} className="rounded border border-champagne/50 bg-champagne/10 px-1.5 py-0.5 text-[9px] font-semibold text-champagne">{reason}</span>)}
              </div>
            )}
          </button>
        ))}
        {!items.length && <div className="rounded border border-softgraph bg-ink p-3 text-xs text-taupe">No stalled, blocked, review, or input items.</div>}
      </div>
      {backupAttention && (
        <button onClick={() => onNavigate('mission-control')} className="mt-4 w-full rounded border border-clay/70 bg-clay/10 p-3 text-left text-xs hover:border-clay">
          <div className="font-semibold text-clay">Backup needs attention</div>
          <div className="mt-1 text-taupe">{backup.state === 'failed' ? 'Latest backup failed.' : 'Latest backup is older than 48 hours.'}</div>
        </button>
      )}
      <div className="mt-5 rounded border border-softgraph bg-ink p-3 text-xs text-taupe">
        <div className="font-mono text-champagne">TOKENS</div>
        <div className="mt-2">{strip.current_task?.label || 'Token usage: unavailable from current CLI output'}</div>
        <div className="mt-1">{strip.last_task?.label || 'Token usage: unavailable from current CLI output'}</div>
        <div className="mt-1">{strip.today?.label || 'Token usage: unavailable from current CLI output'}</div>
      </div>
      <button onClick={() => onNavigate('mission-control')} className="mt-4 text-xs font-semibold text-champagne hover:text-stone">Open Mission Control</button>
    </aside>
  )
}

export function ConfirmModal({ action, onCancel, onConfirm }) {
  if (!action) return null
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/80 p-4">
      <div className="w-full max-w-md rounded border border-clay/60 bg-graphite p-5">
        <div className="flex items-center gap-2 text-clay"><LockKeyhole size={16} /><h3 className="font-semibold">Typed confirm required</h3></div>
        <p className="mt-3 text-sm text-taupe">This external action is stubbed in Dashboard v1. Type confirm to acknowledge the gate.</p>
        <div className="mt-4 flex justify-end gap-2">
          <ActionButton onClick={onCancel}>Cancel</ActionButton>
          <ActionButton kind="locked" onClick={onConfirm}>confirm</ActionButton>
        </div>
      </div>
    </div>
  )
}
