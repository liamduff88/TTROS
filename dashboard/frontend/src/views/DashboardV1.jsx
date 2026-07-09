import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Columns3, Copy, Database, Edit3, ExternalLink, FolderOpen, GitBranch, Layers, Play, Plus, RefreshCw, Save, Search, Settings, Shield, Workflow, X } from 'lucide-react'
import {
  attachQueueReceipt,
  closeQueueItemReview,
  createDashboardTask,
  createQueueItem,
  getDashboardCockpit,
  getDashboardGraphify,
  getDashboardMemory,
  getDashboardPrompts,
  getDashboardRepoIngest,
  getDashboardResults,
  getDashboardSkills,
  getDashboardTokens,
  getDashboardWorkflows,
  getQueueItems,
  openDashboardPath,
  saveDashboardSkill,
} from '../api'
import { ActionButton, DetailPanel, EmptyState, FilterBar, PageHeader, RowButton, SourceChip, StatTile, StatusChip, statusLabel } from '../components/DashboardKit'

const age = value => {
  if (!value) return 'unavailable'
  const diff = Date.now() - new Date(value).getTime()
  if (Number.isNaN(diff)) return 'unavailable'
  const hours = Math.max(0, Math.round(diff / 36e5))
  return hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`
}

const itemLane = item => item?.lane || item?.owner || 'unassigned'
const textMatch = (item, q) => !q || JSON.stringify(item).toLowerCase().includes(q.toLowerCase())
const byFilters = (item, filters) =>
  (!filters.status || item.status === filters.status) &&
  (!filters.lane || itemLane(item) === filters.lane || item.owner === filters.lane) &&
  (!filters.workbench || item.owner === filters.workbench) &&
  (!filters.source || String(item.source || '').toLowerCase() === filters.source.toLowerCase()) &&
  textMatch(item, filters.q || '')

const backupLabel = state => ({
  no_receipts: 'No receipts',
  fresh_success: 'Fresh success',
  stale: 'Stale',
  failed: 'Failed',
}[state] || 'Unavailable')

function BackupStatusCard({ backup }) {
  const latest = backup?.latest
  const attention = backup?.needs_attention
  return (
    <div className={`rounded border p-4 ${attention ? 'border-clay/70 bg-clay/10' : 'border-softgraph bg-graphite/70'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-stone">Automated Backup</h2>
          <div className="mt-1 text-xs text-taupe">{backup?.token_usage_text || 'Token usage: no agent invocation'}</div>
        </div>
        <StatusChip status={attention ? 'Blocked' : 'Done'}>{backupLabel(backup?.state)}</StatusChip>
      </div>
      <div className="mt-3 grid gap-2 text-xs text-taupe md:grid-cols-2">
        <div><span className="text-stone">Last:</span> {latest?.ts || 'no backup receipts yet'}</div>
        <div><span className="text-stone">Target:</span> {latest?.target || 'D:\\TTROS_Backups'}</div>
        <div className="md:col-span-2"><span className="text-stone">Snapshot:</span> {latest?.snapshot_path || 'unavailable'}</div>
        <div className="md:col-span-2"><span className="text-stone">Receipt:</span> {backup?.latest_receipt_path || 'queue/receipts/backups.jsonl'}</div>
        <div className="md:col-span-2"><span className="text-stone">Log:</span> {backup?.latest_log_path || 'unavailable'}</div>
      </div>
    </div>
  )
}

function useAsync(loader, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: '' })
  useEffect(() => {
    let alive = true
    setState(prev => ({ ...prev, loading: true, error: '' }))
    loader().then(data => alive && setState({ loading: false, data, error: '' })).catch(error => alive && setState({ loading: false, data: null, error: error.message || 'Unavailable' }))
    return () => { alive = false }
  }, deps)
  return state
}

function MarkdownPreview({ content }) {
  return <pre className="max-h-[65vh] overflow-auto whitespace-pre-wrap rounded border border-softgraph bg-ink p-3 text-xs leading-5 text-stone">{content || 'unavailable'}</pre>
}

export function Cockpit({ cockpit, onNavigate, refresh }) {
  const [selected, setSelected] = useState(null)
  const data = cockpit || {}
  const counts = data.counts || {}
  const needs = data.needs_me || []
  const recent = data.recent_output || []
  return (
    <>
      <PageHeader title="Cockpit" question="What needs me right now, and what is the OS doing/spending?" actions={<ActionButton onClick={refresh}><RefreshCw size={13} />Refresh</ActionButton>} />
      <section className="rounded border border-champagne/40 bg-graphite p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-xs font-mono text-champagne">NEEDS ME</div>
            <div className="mt-1 text-3xl font-semibold text-ivory">{needs.length} items</div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <StatTile label="Needs Me" value={counts.human_review || 0} onClick={() => onNavigate('work-queue', { status: 'human_review' })} />
            <StatTile label="Blocked" value={counts.blocked || 0} onClick={() => onNavigate('work-queue', { status: 'blocked' })} />
            <StatTile label="Needs Input" value={counts.needs_input || 0} onClick={() => onNavigate('work-queue', { status: 'needs_input' })} />
          </div>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {needs.slice(0, 6).map(item => (
            <RowButton key={item.id} title={item.title} meta={`${item.id} · ${itemLane(item)} · ${age(item.updated_at || item.created_at)}`} right={<><SourceChip source={item.source} /><StatusChip status={item.status} /></>} onClick={() => setSelected(item)} />
          ))}
          {!needs.length && <EmptyState title="Nothing needs you." detail="No human_review, needs_input, or blocked queue items are active." />}
        </div>
      </section>
      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-softgraph bg-graphite/70 p-4">
          <h2 className="mb-3 text-sm font-semibold text-stone">Queue Snapshot</h2>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'blocked', 'done'].map(status => (
              <StatTile key={status} label={statusLabel(status)} value={counts[status] || 0} sub={status} onClick={() => onNavigate('work-queue', { status })} />
            ))}
          </div>
        </div>
        <BackupStatusCard backup={data.backup} />
      </section>
      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-softgraph bg-graphite/70 p-4">
          <h2 className="mb-3 text-sm font-semibold text-stone">Workbench Tiles</h2>
          <div className="grid gap-2 md:grid-cols-2">
            {(data.workbenches || []).map(tile => (
              <button key={tile.id} onClick={() => tile.id === 'graphify' ? onNavigate('graphify') : onNavigate('work-queue', { workbench: tile.id.replace('-code', '') })} className="rounded border border-softgraph bg-ink p-3 text-left hover:border-champagne/40">
                <div className="flex justify-between gap-2"><span className="text-sm font-semibold text-stone">{tile.name}</span><StatusChip status={tile.status} /></div>
                <div className="mt-2 truncate text-xs text-taupe">{tile.last_task}</div>
                <div className="mt-2 text-xs text-champagne">Tokens: {typeof tile.tokens_today === 'number' ? tile.tokens_today.toLocaleString() : 'unavailable'}</div>
              </button>
            ))}
          </div>
        </div>
      </section>
      <section className="mt-4 rounded border border-softgraph bg-graphite/70 p-4">
        <h2 className="mb-3 text-sm font-semibold text-stone">Recent Output</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {recent.slice(0, 6).map(item => <RowButton key={item.id} title={item.title} meta={`${item.source} · ${item.path}`} onClick={() => setSelected(item)} />)}
        </div>
      </section>
      <DetailPanel item={selected} title={selected?.title} subtitle={selected?.id || selected?.path} onClose={() => setSelected(null)}>
        {selected?.status && <div className="mb-3 flex gap-2"><StatusChip status={selected.status} /><SourceChip source={selected.source} /></div>}
        <MarkdownPreview content={selected?.preview || selected?.context || JSON.stringify(selected, null, 2)} />
      </DetailPanel>
    </>
  )
}

export function WorkQueueV1({ initialFilters = {} }) {
  const [filters, setFilters] = useState(initialFilters)
  const [selected, setSelected] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ title: '', owner: 'hermes', priority: 'normal', source: 'dashboard', tags: '', context: '', definition_of_done: '' })
  const [note, setNote] = useState('')
  const [message, setMessage] = useState('')
  const load = () => { setLoading(true); getQueueItems().then(data => setItems(data.items || [])).finally(() => setLoading(false)) }
  useEffect(load, [])
  useEffect(() => setFilters(initialFilters), [JSON.stringify(initialFilters)])
  const filtered = useMemo(() => items.filter(item => byFilters(item, filters)), [items, filters])
  const columns = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'blocked', 'done']
  const create = async event => {
    event.preventDefault()
    const result = await createQueueItem(form)
    setMessage(`Created ${result.item?.id || 'queue item'}`)
    setForm({ ...form, title: '', context: '' })
    load()
  }
  const close = async status => {
    const result = await closeQueueItemReview(selected.id, { status, review_note: note })
    setMessage(result.telegram_reply ? `Closed ${selected.id}; Telegram reply mock logged` : `Closed ${selected.id}`)
    setSelected(result.item)
    load()
  }
  return (
    <>
      <PageHeader title="Work Queue" question="What work exists and where is it stuck?" actions={<ActionButton onClick={load}>{loading ? 'Loading' : 'Refresh'}</ActionButton>} />
      <FilterBar filters={filters} onChange={setFilters} />
      <div className="grid gap-3 xl:grid-cols-7">
        {columns.map(status => (
          <div key={status} className="min-h-80 rounded border border-softgraph bg-graphite/60 p-3">
            <div className="mb-3 flex justify-between text-xs"><span className="font-semibold text-stone">{statusLabel(status)}</span><span className="text-taupe">{filtered.filter(item => item.status === status).length}</span></div>
            <div className="space-y-2">
              {filtered.filter(item => item.status === status).slice(0, status === 'done' ? 5 : 30).map(item => (
                <button key={item.id} onClick={() => setSelected(item)} className="w-full rounded border border-softgraph bg-ink p-2 text-left hover:border-champagne/40">
                  <div className="line-clamp-2 text-xs font-semibold text-stone">{item.title}</div>
                  <div className="mt-2 flex flex-wrap gap-1"><SourceChip source={item.source} /><span className="text-[10px] text-taupe">{item.id}</span></div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={create} className="mt-4 rounded border border-softgraph bg-graphite/70 p-4">
        <h2 className="mb-3 text-sm font-semibold text-stone">Create Queue Item</h2>
        <div className="grid gap-2 md:grid-cols-4">
          <input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Title" className="rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone md:col-span-2" />
          <select value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} className="rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone">{['hermes', 'codex', 'claude', 'revenue', 'marketing', 'delivery', 'operations', 'unassigned'].map(v => <option key={v}>{v}</option>)}</select>
          <select value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })} className="rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone">{['low', 'normal', 'high', 'urgent'].map(v => <option key={v}>{v}</option>)}</select>
          <textarea value={form.context} onChange={e => setForm({ ...form, context: e.target.value })} placeholder="Context" className="min-h-20 rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone md:col-span-4" />
        </div>
        <div className="mt-3 flex items-center gap-3"><ActionButton kind="primary" type="submit"><Plus size={14} />Create</ActionButton><span className="text-xs text-champagne">{message}</span></div>
      </form>
      <DetailPanel item={selected} title={selected?.title} subtitle={selected?.id} onClose={() => setSelected(null)}>
        <div className="mb-3 flex flex-wrap gap-2"><StatusChip status={selected?.status} /><SourceChip source={selected?.source} /><span className="text-xs text-taupe">{itemLane(selected)}</span></div>
        <MarkdownPreview content={JSON.stringify(selected, null, 2)} />
        {selected?.status === 'human_review' && <div className="mt-4 rounded border border-softgraph bg-ink p-3">
          <textarea value={note} onChange={e => setNote(e.target.value)} placeholder="Close note" className="min-h-20 w-full rounded border border-softgraph bg-graphite px-3 py-2 text-sm text-stone" />
          <div className="mt-3 flex flex-wrap gap-2"><ActionButton onClick={() => close('done')}>Close Done</ActionButton><ActionButton onClick={() => close('needs_input')}>Needs Input</ActionButton><ActionButton onClick={() => close('blocked')}>Blocked</ActionButton></div>
        </div>}
      </DetailPanel>
    </>
  )
}

function FileBoard({ title, question, loader, listKey, renderMeta, tokenAction }) {
  const { loading, data, error } = useAsync(loader)
  const [filters, setFilters] = useState({})
  const [selected, setSelected] = useState(null)
  const items = (data?.[listKey] || data?.items || []).filter(item => textMatch(item, filters.q || '') && (!filters.lane || item.lane === filters.lane) && (!filters.status || item.state === filters.status || item.status === filters.status))
  return (
    <>
      <PageHeader title={title} question={question} />
      <FilterBar filters={filters} onChange={setFilters} />
      {loading && <EmptyState title="Loading" detail="Reading local files." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {items.map(item => <RowButton key={item.id || item.path} title={item.name || item.title} meta={renderMeta?.(item) || item.path} right={item.state && <StatusChip status={item.state === 'earned' ? 'Done' : 'Ready'}>{item.state}</StatusChip>} onClick={() => setSelected(item)} />)}
      </div>
      {!loading && !items.length && <EmptyState title="No local entries" detail="Nothing matched the current filters." />}
      <DetailPanel item={selected} title={selected?.name || selected?.title} subtitle={selected?.path || selected?.id} onClose={() => setSelected(null)}>
        <div className="mb-3 flex flex-wrap gap-2">{tokenAction && <ActionButton kind="token" onClick={() => tokenAction(selected)}>Create queue item</ActionButton>}<ActionButton onClick={() => navigator.clipboard?.writeText(selected?.content || '')}><Copy size={13} />Copy</ActionButton></div>
        <MarkdownPreview content={selected?.content || selected?.preview || JSON.stringify(selected, null, 2)} />
      </DetailPanel>
    </>
  )
}

export function WorkflowBench() {
  const run = item => createDashboardTask({ title: `Run workflow: ${item.name}`, owner: item.lane === 'operations' ? 'operations' : item.lane, tags: `workflow,${item.id}`, context: `Run workflow from ${item.path}.`, sources: item.path, definition_of_done: 'Workflow run is completed with receipt and token usage block.' })
  return <FileBoard title="Workflow Bench" question="What repeatable workflows do I have, and how do I run one now?" loader={getDashboardWorkflows} listKey="workflows" renderMeta={item => `${item.lane} · receipts ${item.receipt_count} · avg tokens ${item.avg_tokens}`} tokenAction={run} />
}

export function SkillsBoard() {
  const [filters, setFilters] = useState({})
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({ name: '', description: '', body: '' })
  const [command, setCommand] = useState('')
  const [message, setMessage] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const { loading, data, error } = useAsync(getDashboardSkills, [reloadKey])
  const skills = (data?.skills || []).filter(item =>
    textMatch(item, filters.q || '') &&
    (!filters.lane || item.lane === filters.lane) &&
    (!filters.status || item.status === filters.status || item.state === filters.status)
  )
  const ownerFor = item => item?.lane === 'ops' ? 'operations' : item?.lane || 'delivery'
  const createSkillTask = async item => {
    const result = await createDashboardTask({
      title: `Create task using skill: ${item.name}`,
      owner: ownerFor(item),
      tags: `skill,${item.id}`,
      context: `Use skill from ${item.path}.`,
      sources: item.path,
      definition_of_done: 'Task using selected skill is completed with receipt.',
    })
    setMessage(`Created ${result.item?.id || 'queue item'}`)
  }
  const startEdit = () => {
    setEditForm({ name: selected?.name || '', description: selected?.description || '', body: selected?.body || selected?.content || '' })
    setEditing(true)
    setMessage('')
  }
  const cancelEdit = () => {
    setEditing(false)
    setEditForm({ name: '', description: '', body: '' })
  }
  const saveEdit = async () => {
    const saved = await saveDashboardSkill({ path: selected.path, ...editForm })
    const updated = { ...selected, name: saved.name, title: saved.name, description: saved.description, body: saved.body, content: saved.body, preview: saved.body }
    setSelected(updated)
    setEditing(false)
    setMessage(`Saved ${saved.path}`)
    setReloadKey(key => key + 1)
  }
  const openPath = async kind => {
    const result = await openDashboardPath({ path: selected.path, kind })
    setMessage(`Opened ${result.path}`)
  }
  const createMaintenanceTask = async event => {
    event.preventDefault()
    const text = command.trim()
    if (!text) return
    const result = await createDashboardTask({
      title: `Skills Board maintenance: ${text.slice(0, 80)}`,
      owner: 'codex',
      tags: 'dashboard,skills-board,maintenance',
      context: text,
      sources: selected?.path || 'dashboard/frontend/src/views/DashboardV1.jsx',
      definition_of_done: 'Dashboard Skills Board maintenance queue item is resolved with validation.',
    })
    setMessage(`Created ${result.item?.id || 'queue item'}`)
    setCommand('')
  }
  return (
    <>
      <PageHeader title="Skills Board" question="Which skills are earning their keep?" actions={<ActionButton onClick={() => setReloadKey(key => key + 1)}><RefreshCw size={13} />Refresh</ActionButton>} />
      <FilterBar filters={filters} onChange={setFilters} />
      <form onSubmit={createMaintenanceTask} className="mb-4 rounded border border-softgraph bg-graphite/70 p-4">
        <div className="grid gap-2 md:grid-cols-[1fr_auto]">
          <input value={command} onChange={event => setCommand(event.target.value)} placeholder="Queue dashboard or skill maintenance" className="h-9 rounded border border-softgraph bg-ink px-3 text-sm text-stone placeholder:text-taupe" />
          <ActionButton kind="primary" type="submit"><Plus size={14} />Create Queue Item</ActionButton>
        </div>
        {message && <div className="mt-2 text-xs text-champagne">{message}</div>}
      </form>
      {loading && <EmptyState title="Loading" detail="Reading local skills." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {skills.map(item => (
          <RowButton
            key={item.id || item.path}
            title={item.name || item.id}
            meta={`${item.description || 'No description'} · ${item.lane || 'delivery'} · uses ${item.real_uses}/${item.uses}`}
            right={<StatusChip status={item.state === 'earned' ? 'Done' : 'Ready'}>{item.status || item.state}</StatusChip>}
            onClick={() => { setSelected(item); setEditing(false); setMessage('') }}
          />
        ))}
      </div>
      {!loading && !skills.length && <EmptyState title="No local entries" detail="Nothing matched the current filters." />}
      <DetailPanel item={selected} title={selected?.name || selected?.id} subtitle={selected?.path} onClose={() => { setSelected(null); setEditing(false) }}>
        <div className="mb-3 flex flex-wrap gap-2">
          {!editing && <ActionButton kind="token" onClick={() => createSkillTask(selected)}>Create queue item</ActionButton>}
          {!editing && <ActionButton onClick={startEdit}><Edit3 size={13} />Edit</ActionButton>}
          {editing && <ActionButton kind="primary" onClick={saveEdit}><Save size={13} />Save</ActionButton>}
          {editing && <ActionButton onClick={cancelEdit}><X size={13} />Cancel</ActionButton>}
          {!editing && <ActionButton onClick={() => openPath('file')}><ExternalLink size={13} />Open file</ActionButton>}
          {!editing && <ActionButton onClick={() => openPath('folder')}><FolderOpen size={13} />Open folder</ActionButton>}
          {!editing && <ActionButton onClick={() => navigator.clipboard?.writeText(selected?.body || selected?.content || '')}><Copy size={13} />Copy</ActionButton>}
        </div>
        <div className="mb-3 flex flex-wrap gap-2">
          <SourceChip source={selected?.source || 'skill'} />
          <StatusChip status={selected?.state === 'earned' ? 'Done' : 'Ready'}>{selected?.status || selected?.state}</StatusChip>
          {selected?.trust && <span className="rounded border border-softgraph bg-softgraph/40 px-1.5 py-0.5 text-[10px] text-taupe">trust {selected.trust}</span>}
          {selected?.version && <span className="rounded border border-softgraph bg-softgraph/40 px-1.5 py-0.5 text-[10px] text-taupe">{selected.version}</span>}
        </div>
        {editing ? (
          <div className="space-y-3">
            <input value={editForm.name} onChange={event => setEditForm({ ...editForm, name: event.target.value })} className="w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone" />
            <textarea value={editForm.description} onChange={event => setEditForm({ ...editForm, description: event.target.value })} className="min-h-20 w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone" />
            <textarea value={editForm.body} onChange={event => setEditForm({ ...editForm, body: event.target.value })} className="min-h-[52vh] w-full rounded border border-softgraph bg-ink px-3 py-2 font-mono text-xs leading-5 text-stone" />
          </div>
        ) : (
          <>
            {selected?.description && <div className="mb-3 rounded border border-softgraph bg-ink p-3 text-sm text-stone">{selected.description}</div>}
            <MarkdownPreview content={selected?.body || selected?.content || selected?.preview || JSON.stringify(selected, null, 2)} />
          </>
        )}
      </DetailPanel>
    </>
  )
}

export function ResultsReceipts() {
  return <FileBoard title="Results & Receipts" question="What happened, and is it safe to close?" loader={getDashboardResults} listKey="items" renderMeta={item => `${item.source} · ${age(item.modified)} · ${item.path}`} />
}

export function TokensROI() {
  const { data, loading, error } = useAsync(getDashboardTokens)
  const records = data?.records || []
  return (
    <>
      <PageHeader title="Tokens & ROI" question="Where is my token money going and is it worth it?" />
      {loading && <EmptyState title="Loading" detail="Reading queue/token_ledger.jsonl." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      {data && <div className="grid gap-4 xl:grid-cols-3">
        {['today', 'week', 'month'].map(period => <StatTile key={period} label={period} value={data.periods?.[period]?.known ? Number(data.periods[period].tokens).toLocaleString() : 'unavailable'} sub={`cost ${data.periods?.[period]?.known ? `$${Number(data.periods[period].cost).toFixed(2)}` : 'unavailable'}`} />)}
        <div className="rounded border border-softgraph bg-graphite/70 p-4 xl:col-span-3">
          <h2 className="mb-3 text-sm font-semibold text-stone">Spend Over Time</h2>
          <div className="flex h-40 items-end gap-2 border-b border-softgraph">
            {(data.chart || []).map(day => <div key={day.date} className="flex flex-1 flex-col items-center gap-2"><div className="w-full rounded-t bg-champagne" style={{ height: `${Math.max(4, day.tokens / Math.max(1, Math.max(...data.chart.map(d => d.tokens))) * 130)}px` }} /><span className="text-[10px] text-taupe">{day.date.slice(5)}</span></div>)}
          </div>
        </div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4 xl:col-span-3">
          <h2 className="mb-3 text-sm font-semibold text-stone">Ledger Rows</h2>
          <div className="space-y-2">{records.map((row, index) => <div key={`${row.item_id}-${index}`} className="grid gap-2 rounded border border-softgraph bg-ink p-2 text-xs text-taupe md:grid-cols-6"><span className="text-stone">{row.item_id}</span><span>{row.lane}</span><span>{row.profile}</span><span>{row.model_confirmed || 'unavailable'}</span><span>{row.token_usage?.totals ? Number((row.token_usage.totals.input || 0) + (row.token_usage.totals.output || 0)).toLocaleString() : 'unavailable'}</span><span>{row.token_usage?.unavailable?.length ? 'unavailable parts' : `$${Number(row.token_usage?.est_cost_usd || 0).toFixed(2)}`}</span></div>)}</div>
        </div>
      </div>}
    </>
  )
}

export function MemoryBoard() {
  return <FileBoard title="Memory Board" question="Is the Business Brain current, and what's waiting to be promoted?" loader={getDashboardMemory} listKey="files" renderMeta={item => `${item.path} · ${item.revisit || 'Revisit unavailable'}`} />
}

export function ConnectionsSpine() {
  const connectors = ['Gmail', 'Calendar', 'Drive', 'Docs', 'Sheets', 'GitHub', 'LinkedIn', 'YouTube', 'Instagram', 'Maps', 'Agent Mail', 'Reddit', 'GHL-later']
  return (
    <>
      <PageHeader title="Connections / Spine" question="What can the OS reach, and what's safe to do?" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{connectors.map(name => <div key={name} className="rounded border border-softgraph bg-graphite/70 p-4"><div className="flex justify-between"><span className="font-semibold text-stone">{name}</span><StatusChip status="Unavailable" /></div><div className="mt-2 text-xs text-taupe">Status check unavailable from this local pass.</div><div className="mt-3 flex gap-2"><ActionButton>Check status</ActionButton><ActionButton kind="token">Prepare draft</ActionButton></div></div>)}</div>
    </>
  )
}

export function PromptLibrary() {
  const run = item => createDashboardTask({ title: `Queue item from prompt: ${item.title}`, owner: item.target?.toLowerCase().includes('codex') ? 'codex' : item.target?.toLowerCase().includes('claude') ? 'claude' : 'hermes', tags: 'prompt-library', context: `Use prompt from ${item.path}.`, sources: item.path })
  return <FileBoard title="Prompt Library" question="What stored prompt do I reuse instead of rewriting?" loader={getDashboardPrompts} listKey="prompts" renderMeta={item => `${item.category} · ${item.target}`} tokenAction={run} />
}

export function GraphifyPage() {
  const { data } = useAsync(getDashboardGraphify)
  return <><PageHeader title="Graphify" question="What does the OS/repo knowledge structure look like?" /><div className="min-h-[65vh] rounded border border-softgraph bg-graphite/70 p-4"><EmptyState title={data?.status || 'Unavailable'} detail="Graphify is not embedded in this pass. Use the local launch button when the service exists." action={<ActionButton>Launch Graphify</ActionButton>} /></div></>
}

export function RepoIngest() {
  const { data } = useAsync(getDashboardRepoIngest)
  const reconstitute = () => createDashboardTask({ title: 'Reconstitute quarantined repo', owner: 'codex', tags: 'repo-ingest,reconstitute', context: 'Run the documented repo reconstitution skill from a quarantined repo. Do not execute quarantine code.', definition_of_done: 'Clean reconstituted repo and provenance note are produced.' })
  return <><PageHeader title="Repo Ingest" question="How do I get an outside GitHub repo safely into my system?" actions={<ActionButton kind="token" onClick={reconstitute}>Reconstitute</ActionButton>} /><div className="rounded border border-softgraph bg-graphite/70 p-5"><div className="grid gap-2 md:grid-cols-5">{(data?.steps || []).map((step, i) => <div key={step} className="rounded border border-softgraph bg-ink p-4 text-center"><div className="text-xs text-champagne">{i + 1}</div><div className="mt-1 text-sm font-semibold text-stone">{step}</div></div>)}</div><p className="mt-4 text-sm text-taupe">{data?.note}</p></div></>
}

export function SettingsLaunchers() {
  return <><PageHeader title="Settings / Launchers" question="Local launch commands and dashboard preferences." /><div className="grid gap-3 md:grid-cols-2"><EmptyState title="Hermes" detail="Use existing WSL launcher routes from the old Agent Workbench." action={<ActionButton>Open launcher</ActionButton>} /><EmptyState title="Telegram bridge" detail="Read-only status; no bridge code changes in this pass." action={<ActionButton>Check status</ActionButton>} /></div></>
}
