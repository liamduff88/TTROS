import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Columns3, Copy, Database, Edit3, ExternalLink, FolderOpen, GitBranch, Layers, Play, Plus, RefreshCw, Save, Search, Settings, Shield, Workflow, X } from 'lucide-react'
import {
  attachQueueReceipt,
  createCockpitCommand,
  createDashboardTask,
  createQueueItem,
  getDashboardCockpit,
  getDashboardGraphify,
  fetchGraphifyRepository,
  getGraphifyArtifactText,
  getLatitudeStatus,
  getHermesUiStatus,
  getDashboardMemory,
  getDashboardPrompts,
  getDashboardRepoIngest,
  getDashboardResults,
  getDashboardSkills,
  getDashboardTokens,
  getDashboardWorkflows,
  getDashboardWorkflow,
  getQueueItems,
  launchHermesUi,
  openDashboardPath,
  queueGraphifyModelWork,
  rebuildGraphifyRepository,
  refetchGraphifyRepository,
  runGraphifyAction,
  saveDashboardSkill,
  saveDashboardWorkflow,
} from '../api'
import { HumanReviewCard } from '../components/HumanReviewCard'
import { validateGitHubRepositoryUrl } from '../graphifyState'
import { launcherPrompt } from '../launcherPrompts'
import { laneRoutePath } from '../shellState'
import { sourceComponentTotalText, tokenComponentText } from '../tokenDisplay'
import { ActionButton, DetailPanel, EmptyState, FilterBar, PageHeader, RowButton, SourceChip, StatTile, StatusChip, statusLabel } from '../components/DashboardKit'

const age = value => {
  if (!value) return 'unavailable'
  const diff = Date.now() - new Date(value).getTime()
  if (Number.isNaN(diff)) return 'unavailable'
  const hours = Math.max(0, Math.round(diff / 36e5))
  return hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`
}

const itemLane = item => item?.lane || item?.owner || 'unassigned'

const laneColor = lane => `var(--lane-${lane === 'unassigned' ? 'unassigned' : lane})`
const laneTitle = lane => lane === 'unassigned' ? 'Unassigned' : `${lane.slice(0, 1).toUpperCase()}${lane.slice(1)}`
const laneTokenText = usage => usage?.state === 'exact'
  ? `${Number(usage.total).toLocaleString()} exact · ${Number(usage.input).toLocaleString()} in / ${Number(usage.output).toLocaleString()} out`
  : 'unavailable'

function LaneActivityCard({ lane, onNavigate }) {
  const items = lane.items || []
  const active = lane.current_assigned_work || []
  const review = Number(lane.counts?.human_review || 0)
  const border = review ? 'var(--needs-review)' : `var(--wb-${lane.shortcut?.workbench || 'hermes'}-queued)`
  const href = laneRoutePath(lane.lane) || '/'
  return (
    <a
      href={href}
      onClick={event => { event.preventDefault(); onNavigate('work-queue', { lane: lane.lane }) }}
      className="block min-w-0 rounded border bg-graphite/70 p-3 text-left hover:border-champagne/40 focus:outline-none focus:ring-2 focus:ring-champagne/50"
      style={{ borderColor: border }}
      data-lane-card={lane.lane}
      aria-label={`Open ${laneTitle(lane.lane)} lane`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-ivory" style={{ backgroundColor: laneColor(lane.lane) }}>{laneTitle(lane.lane)}</span>
          <div className="mt-2 text-xs text-taupe">{items.length} queue items · {lane.degraded ? 'data unavailable' : 'live local data'}</div>
        </div>
        {review > 0 && <StatusChip status="human_review">Needs review</StatusChip>}
      </div>
      <div className="mt-3 grid grid-cols-4 gap-1 text-center text-[10px] text-taupe">
        {['agent_todo', 'agent_working', 'blocked', 'human_review'].map(status => <div key={status} className="rounded bg-ink p-1.5"><strong className="block text-sm text-stone">{lane.counts?.[status] || 0}</strong>{status.replace('agent_', '').replace('_', ' ')}</div>)}
      </div>
      <div className="mt-3 space-y-2 text-xs">
        <div><span className="text-taupe">Current:</span> <span className="text-stone">{active.length ? active.map(item => item.id).join(', ') : 'none assigned'}</span></div>
        <div><span className="text-taupe">Last done:</span> <span className="text-stone">{lane.last_completed_item?.id || 'unavailable'}</span></div>
        <div className="truncate"><span className="text-taupe">Receipt:</span> <span className="text-stone">{lane.latest_receipt?.path || 'unavailable'}</span></div>
        <div className="truncate"><span className="text-taupe">Artifact:</span> <span className="text-stone">{lane.latest_artifact?.path || 'unavailable'}</span></div>
        <div><span className="text-taupe">Tokens:</span> <span className="text-stone">{laneTokenText(lane.token_usage)}</span></div>
        <div><span className="text-taupe">Last run:</span> <span className="text-stone">{lane.last_successful_run ? (lane.last_successful_run.timestamp || lane.last_successful_run.completed_at || lane.last_successful_run.created_at || 'recorded') : 'unavailable'}</span></div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1">
        {items.slice(0, 8).map(item => <span key={item.id} className="rounded border border-softgraph bg-ink px-1.5 py-1 text-[10px] text-taupe" data-lane-item={item.id}>{item.id} · {item.owner || 'unassigned'} / {item.workbench || 'no workbench'}</span>)}
      </div>
    </a>
  )
}
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
  const [command, setCommand] = useState('')
  const [commandState, setCommandState] = useState({ busy: false, message: '', error: '' })
  const data = cockpit || {}
  const counts = data.counts || {}
  const needs = data.needs_me || []
  const recent = data.recent_output || []
  const laneActivity = data.lane_activity || []
  const submitCommand = async event => {
    event.preventDefault()
    const text = command.trim()
    if (!text || commandState.busy) return
    setCommandState({ busy: true, message: '', error: '' })
    try {
      const result = await createCockpitCommand(text)
      if (!result?.item?.id) throw new Error('Local queue item was not created')
      setCommand('')
      setCommandState({ busy: false, message: `${result.item.id} routed to ${result.item.owner}.`, error: '' })
      await refresh?.()
      onNavigate('work-queue', { selectedId: result.item.id })
    } catch (error) {
      setCommandState({ busy: false, message: '', error: error?.response?.data?.detail || error?.message || 'Command could not be queued' })
    }
  }
  return (
    <>
      <PageHeader title="Cockpit" question="What needs me right now, and what is the OS doing/spending?" actions={<ActionButton onClick={refresh}><RefreshCw size={13} />Refresh</ActionButton>} />
      <form onSubmit={submitCommand} className="mb-4 rounded border border-champagne/40 bg-graphite p-4" data-testid="cockpit-command-input">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <label className="min-w-0 flex-1">
            <span className="text-xs font-mono text-champagne">COMMAND THE OS</span>
            <textarea
              value={command}
              onChange={event => { setCommand(event.target.value); setCommandState(current => ({ ...current, message: '', error: '' })) }}
              maxLength={2000}
              placeholder="Describe the work in plain language"
              className="mt-2 min-h-20 w-full resize-y rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne/60"
            />
          </label>
          <ActionButton kind="primary" type="submit" disabled={commandState.busy || !command.trim()}>
            <Plus size={14} />{commandState.busy ? 'Routing…' : 'Add to Work Queue'}
          </ActionButton>
        </div>
        <p className="mt-2 text-xs text-taupe">Deterministic local intake only. This creates a routed work item; it does not call a model or take external action.</p>
        {(commandState.message || commandState.error) && <div className={`mt-2 text-xs font-mono ${commandState.error ? 'text-clay' : 'text-champagne'}`}>{commandState.error || commandState.message}</div>}
      </form>
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
      <section className="mt-4 rounded border border-softgraph bg-graphite/50 p-4" data-testid="lane-activity">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-stone">Lane Activity</h2>
          <p className="mt-1 text-xs text-taupe">Queue drilldowns grouped by recorded lane tag or lane owner; workbench and status remain separate real fields.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {laneActivity.map(lane => <LaneActivityCard key={lane.lane} lane={lane} onNavigate={onNavigate} />)}
        </div>
        {!laneActivity.length && <EmptyState title="Lane activity unavailable" detail="The existing queue and ledgers could not be summarized." />}
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
        {selected?.status === 'human_review' && <HumanReviewCard item={selected} className="mt-4" onSaved={async result => { setSelected(result.item); load() }} />}
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
  const [filters, setFilters] = useState({})
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [loaded, setLoaded] = useState(null)
  const [message, setMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const { loading, data, error } = useAsync(getDashboardWorkflows, [reloadKey])
  const workflows = (data?.workflows || []).filter(item => textMatch(item, filters.q || '') && (!filters.lane || item.lane === filters.lane))
  const run = item => createDashboardTask({ title: `Run workflow: ${item.name}`, owner: item.lane === 'operations' ? 'operations' : item.lane, tags: `workflow,${item.id}`, context: `Run workflow from ${item.path}.`, sources: item.path, definition_of_done: 'Workflow run is completed with receipt and token usage block.' })
  const beginEdit = async () => {
    setMessage('')
    setErrorMessage('')
    try {
      const workflow = await getDashboardWorkflow(selected.id)
      setLoaded(workflow)
      setDraft(workflow.content)
      setEditing(true)
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || error.message || 'Workflow load failed')
    }
  }
  const cancelEdit = () => {
    setEditing(false)
    setDraft('')
    setLoaded(null)
    setMessage('Edit cancelled; persisted content was not changed.')
  }
  const reloadEdit = async () => {
    setEditing(false)
    await beginEdit()
    setMessage('Reloaded exact persisted content.')
  }
  const saveEdit = async () => {
    setMessage('')
    setErrorMessage('')
    try {
      const saved = await saveDashboardWorkflow({ workflow_id: selected.id, content: draft, expected_revision: loaded.revision })
      setLoaded(saved)
      setDraft(saved.content)
      setSelected(current => ({ ...current, name: saved.name, content: saved.content, revision: saved.revision }))
      setEditing(false)
      setMessage(`Saved and verified ${saved.path}; workflow was not executed.`)
      setReloadKey(key => key + 1)
    } catch (error) {
      setErrorMessage(error?.response?.data?.detail || error.message || 'Workflow save failed')
    }
  }
  const dirty = Boolean(editing && loaded && draft !== loaded.content)
  return (
    <>
      <PageHeader title="Workflow Bench" question="View repeatable workflow sources and safely edit eligible canonical definitions." actions={<ActionButton onClick={() => setReloadKey(key => key + 1)}><RefreshCw size={13} />Refresh</ActionButton>} />
      <FilterBar filters={filters} onChange={setFilters} />
      {loading && <EmptyState title="Loading" detail="Reading local workflow sources." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {workflows.map(item => <RowButton key={item.id} title={item.name} meta={`${item.identifier} · ${item.lane} · ${item.path} · ${item.editable ? 'editable' : 'read-only'}`} onClick={() => { setSelected(item); setEditing(false); setLoaded(null); setMessage(''); setErrorMessage('') }} />)}
      </div>
      {!loading && !workflows.length && <EmptyState title="No local entries" detail="Nothing matched the current filters." />}
      <DetailPanel item={selected} title={selected?.name} subtitle={`${selected?.identifier || selected?.id} · ${selected?.path || ''}`} onClose={() => { setSelected(null); setEditing(false); setLoaded(null) }}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {!editing && <ActionButton kind="token" onClick={() => run(selected)}>Create queue item</ActionButton>}
          {!editing && selected?.editable && <ActionButton onClick={beginEdit}><Edit3 size={13} />Edit source</ActionButton>}
          {editing && <ActionButton kind="primary" onClick={saveEdit} disabled={!dirty}><Save size={13} />Save deliberately</ActionButton>}
          {editing && <ActionButton onClick={reloadEdit}><RefreshCw size={13} />Reload persisted</ActionButton>}
          {editing && <ActionButton onClick={cancelEdit}><X size={13} />Cancel</ActionButton>}
          {!editing && <ActionButton onClick={() => navigator.clipboard?.writeText(selected?.content || '')}><Copy size={13} />Copy</ActionButton>}
          {editing && <span className={`text-xs font-mono ${dirty ? 'text-champagne' : 'text-taupe'}`}>{dirty ? 'Unsaved changes' : 'No changes'}</span>}
        </div>
        {!selected?.editable && <div className="mb-3 rounded border border-softgraph bg-ink p-3 text-xs text-taupe">Read-only: {selected?.read_only_reason || 'No safely resolvable editable source is available.'}</div>}
        {message && <div className="mb-3 rounded border border-olive/40 bg-olive/10 p-2 text-xs text-stone">{message}</div>}
        {errorMessage && <div className="mb-3 rounded border border-clay/50 bg-clay/10 p-2 text-xs text-clay">{errorMessage}</div>}
        {editing ? <textarea aria-label="Workflow source editor" value={draft} onChange={event => setDraft(event.target.value)} className="min-h-[58vh] w-full rounded border border-softgraph bg-ink px-3 py-2 font-mono text-xs leading-5 text-stone outline-none focus:border-champagne/60" /> : <MarkdownPreview content={selected?.content || ''} />}
      </DetailPanel>
    </>
  )
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
  const { data, loading, error } = useAsync(getDashboardResults)
  const [filters, setFilters] = useState({})
  const [selected, setSelected] = useState(null)
  const activity = (data?.activity || []).filter(item =>
    textMatch(item, filters.q || '') &&
    (!filters.lane || item.lane === filters.lane) &&
    (!filters.workbench || item.workbench === filters.workbench) &&
    (!filters.status || item.status === filters.status) &&
    (!filters.source || String(item.source || '').toLowerCase() === filters.source.toLowerCase()) &&
    (!filters.date || String(item.time || '').slice(0, 10) === filters.date)
  )
  return (
    <>
      <PageHeader title="Activity & Receipts" question="Newest-first evidence from existing receipts and ledgers. Read-only; viewing makes no model calls." />
      <FilterBar filters={filters} onChange={setFilters} />
      <div className="mb-4 flex items-center gap-2 rounded border border-softgraph bg-graphite/60 p-3">
        <label className="text-xs text-taupe" htmlFor="activity-date">Date</label>
        <input id="activity-date" type="date" value={filters.date || ''} onChange={event => setFilters({ ...filters, date: event.target.value })} className="h-9 rounded border border-softgraph bg-ink px-2 text-xs text-stone" />
        <span className="ml-auto text-xs text-taupe">{data?.token_usage_text || 'Token usage: no agent invocation'}</span>
      </div>
      {loading && <EmptyState title="Loading" detail="Reading existing receipts and ledgers." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      <div className="space-y-2" data-testid="activity-feed">
        {activity.map(item => (
          <button key={item.path} onClick={() => setSelected(item)} className="grid w-full gap-2 rounded border border-softgraph bg-graphite/60 p-3 text-left text-xs text-taupe hover:border-champagne/40 lg:grid-cols-[1.1fr_.8fr_1fr_.7fr_1.5fr_1.2fr_1.2fr]" data-activity-path={item.path}>
            <span>{item.time || 'time unavailable'}</span>
            <span className="text-stone">{item.component} / {item.lane}</span>
            <span>{item.item_id}</span>
            <StatusChip status={item.status}>{item.status}</StatusChip>
            <span className="truncate text-stone">{item.receipt || item.artifact}</span>
            <span>{item.token_line || 'Token usage: unavailable'}</span>
            <span>{item.next_action}</span>
          </button>
        ))}
        {!loading && !activity.length && <EmptyState title="No activity" detail="No existing evidence matched the current filters." />}
      </div>
      <DetailPanel item={selected} title={selected?.title} subtitle={selected?.path} onClose={() => setSelected(null)}>
        <div className="mb-3 flex flex-wrap gap-2"><SourceChip source={selected?.source} /><StatusChip status={selected?.status}>{selected?.status}</StatusChip><span className="text-xs text-taupe">{selected?.token_line}</span></div>
        <MarkdownPreview content={selected?.preview || 'Preview unavailable.'} />
      </DetailPanel>
    </>
  )
}

export function TokensROI() {
  const { data, loading, error } = useAsync(getDashboardTokens)
  const records = data?.records || []
  const rowTokenTotal = row => {
    const totals = row.token_usage?.totals
    if (!totals || !Number.isFinite(Number(totals.input)) || !Number.isFinite(Number(totals.output))) return 'unavailable'
    const total = Number(totals.input) + Number(totals.output)
    return total > 0 || !row.token_usage?.unavailable?.length ? total.toLocaleString() : 'unavailable'
  }
  const rowCost = row => (row.token_usage?.unavailable || []).some(part => String(part).toLowerCase().includes('cost'))
    ? 'cost unavailable'
    : `$${Number(row.token_usage?.est_cost_usd || 0).toFixed(2)}`
  const periodValue = period => period?.unavailable
    ? period.known ? `${Number(period.tokens || 0).toLocaleString()} known + gaps` : 'unavailable'
    : period?.known ? Number(period.tokens || 0).toLocaleString() : 'unavailable'
  const periodCost = period => period?.unavailable
    ? period.known ? `partial $${Number(period.cost || 0).toFixed(2)}` : 'unavailable'
    : period?.known ? `$${Number(period.cost || 0).toFixed(2)}` : 'unavailable'
  return (
    <>
      <PageHeader title="Tokens & ROI" question="Where is my token money going and is it worth it?" />
      {loading && <EmptyState title="Loading" detail="Reading queue/token_ledger.jsonl." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      {data && <div className="grid gap-4 xl:grid-cols-3">
        {['today', 'week', 'month'].map(period => <StatTile key={period} label={period} value={periodValue(data.periods?.[period])} sub={`cost ${periodCost(data.periods?.[period])}`} />)}
        <div className="rounded border border-softgraph bg-graphite/70 p-4 xl:col-span-3">
          <h2 className="mb-3 text-sm font-semibold text-stone">Spend Over Time</h2>
          <div className="flex h-40 items-end gap-2 border-b border-softgraph">
            {(data.chart || []).map(day => <div key={day.date} className="flex flex-1 flex-col items-center gap-2"><div className="w-full rounded-t bg-champagne" style={{ height: `${Math.max(4, day.tokens / Math.max(1, Math.max(...data.chart.map(d => d.tokens))) * 130)}px` }} /><span className="text-[10px] text-taupe">{day.date.slice(5)}</span></div>)}
          </div>
        </div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4 xl:col-span-3">
          <h2 className="mb-1 text-sm font-semibold text-stone">Usage by actual invocation source</h2>
          <p className="mb-3 text-xs text-taupe">Source is taken only from persisted invocation evidence. Queue owner, lane, profile, workbench classification, and model are not treated as source proof.</p>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{(data.source_summary || []).map(group => <div key={group.source} className="rounded border border-softgraph bg-ink p-3 text-xs text-taupe"><div className="font-semibold text-stone">{group.source}</div><div className="mt-2">Exact rows {group.exact_rows} · estimates {group.estimate_rows} · unavailable {group.unavailable_rows} · deterministic {group.no_agent_invocation_rows}</div><div className="mt-1">Exact only: input {group.input.toLocaleString()} · output {group.output.toLocaleString()} · total {group.total.toLocaleString()}</div><div className="mt-1">Cached input {sourceComponentTotalText(group, 'cached_input', 'cached_input_unavailable_rows')} separate · reasoning {sourceComponentTotalText(group, 'reasoning_output', 'reasoning_output_unavailable_rows')} subset of output</div></div>)}</div>
        </div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4 xl:col-span-3">
          <h2 className="mb-3 text-sm font-semibold text-stone">Invocation ledger · newest first</h2>
          <div className="space-y-2">{records.map((row, index) => <div key={`${row.item_id}-${row.session_id || row.invocation_id || index}`} className="grid gap-2 rounded border border-softgraph bg-ink p-3 text-xs text-taupe lg:grid-cols-[1.1fr_1.1fr_1fr_1.2fr_1fr_1fr]"><span className="text-stone">{row.item_id}<small className="mt-1 block break-all text-taupe">{row.session_id || row.invocation_id || 'session unavailable'}</small></span><span>{row.event_timestamp_utc || `${row.event_timestamp || 'timestamp missing'} · invalid`}</span><span className="text-stone">{row.invocation_source}<small className="mt-1 block text-taupe">{row.invocation_source_evidence}</small></span><span>{row.model_identity || 'unavailable'}<small className="mt-1 block">model identity (separate)</small></span><span>{row.availability_state === 'no_agent_invocation' ? 'No agent invocation' : row.total_tokens === null ? 'Unavailable' : `${Number(row.input_tokens || 0).toLocaleString()} in / ${Number(row.output_tokens || 0).toLocaleString()} out / ${Number(row.total_tokens).toLocaleString()} total`}</span><span>{tokenComponentText(row.cached_input_tokens, 'cached', ' separate')}<small className="mt-1 block">{tokenComponentText(row.reasoning_output_tokens, 'reasoning', ' ⊂ output')}</small><small className="mt-1 block">{rowCost(row)}</small></span></div>)}</div>
        </div>
      </div>}
    </>
  )
}

export function MemoryBoard() {
  const { data, loading, error } = useAsync(getDashboardMemory)
  const [filters, setFilters] = useState({})
  const [selected, setSelected] = useState(null)
  const files = (data?.files || []).filter(item => textMatch(item, filters.q || ''))
  return (
    <>
      <PageHeader title="Memory Board" question="Is the canonical Business Brain available and navigable?" />
      {loading && <EmptyState title="Loading" detail="Reading canonical Business Brain pointers." />}
      {error && <EmptyState title="Unavailable" detail={error} />}
      {data && <div className="mb-4 grid gap-3 md:grid-cols-3">
        <StatTile label="Brain" value={data.brain?.available ? 'Available' : 'Unavailable'} sub={data.brain?.root || 'business_brain:README.md'} />
        <StatTile label="Canonical notes" value={data.brain?.file_count || 0} sub={`${data.brain?.blocked_path_count || 0} backup notes excluded`} />
        <StatTile label="Promotion" value={data.promotion_state?.available ? 'Operational' : 'Unavailable'} sub={data.promotion_state?.reason || 'Promotion status unavailable.'} />
      </div>}
      <FilterBar filters={filters} onChange={setFilters} />
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {files.map(item => <RowButton key={item.id || item.path} title={item.title} meta={`${item.path} · ${item.type || 'untyped'}`} onClick={() => setSelected(item)} />)}
      </div>
      {!loading && !files.length && <EmptyState title="No canonical notes" detail={data?.brain?.error || 'Nothing matched the current filters.'} />}
      <DetailPanel item={selected} title={selected?.title} subtitle={selected?.path} onClose={() => setSelected(null)}>
        <MarkdownPreview content={selected?.preview || 'Preview unavailable.'} />
      </DetailPanel>
    </>
  )
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
  const [data, setData] = useState(null)
  const [selectedId, setSelectedId] = useState('')
  const [state, setState] = useState({ loading: true, operation: '', error: '', message: '' })
  const [actionInputs, setActionInputs] = useState({ query: '', explain: '', affected: '', depth: '2', source: '', target: '' })
  const [actionResult, setActionResult] = useState(null)
  const [documentView, setDocumentView] = useState({ title: '', content: '', loading: false, error: '' })
  const refresh = async preferred => {
    setState(current => ({ ...current, loading: true, error: '' }))
    try {
      const result = await getDashboardGraphify()
      setData(result)
      setSelectedId(current => preferred || (result.repos || []).some(repo => repo.id === current) ? (preferred || current) : result.repos?.[0]?.id || '')
    } catch (error) {
      setState(current => ({ ...current, error: error.response?.data?.detail || error.message || 'Graphify status unavailable.' }))
    } finally {
      setState(current => ({ ...current, loading: false }))
    }
  }
  useEffect(() => { refresh() }, [])
  const selected = (data?.repos || []).find(repo => repo.id === selectedId) || null
  const operate = async (label, fn) => {
    setState(current => ({ ...current, operation: label, error: '', message: '' }))
    try {
      const result = await fn()
      setState(current => ({ ...current, message: result?.item ? `Queue item ${result.item.id} created. No model was started.` : `${label} completed.` }))
      if (label === 'Rebuild') await refresh(selectedId)
      return result
    } catch (error) {
      setState(current => ({ ...current, error: error.response?.data?.detail || error.message || `${label} failed.` }))
      return null
    } finally {
      setState(current => ({ ...current, operation: '' }))
    }
  }
  const runAction = async action => {
    if (!selected) return
    const inputs = action === 'query' ? { question: actionInputs.query, budget: 1200 }
      : action === 'explain' ? { node: actionInputs.explain }
        : action === 'affected' ? { node: actionInputs.affected, depth: Number(actionInputs.depth || 2) }
          : { source: actionInputs.source, target: actionInputs.target }
    const result = await operate(action[0].toUpperCase() + action.slice(1), () => runGraphifyAction(selected.owner, selected.repository, action, inputs))
    if (result) setActionResult(result)
  }
  const showDocument = async (title, url) => {
    setDocumentView({ title, content: '', loading: true, error: '' })
    try {
      const content = await getGraphifyArtifactText(url)
      setDocumentView({ title, content: typeof content === 'string' ? content : JSON.stringify(content, null, 2), loading: false, error: '' })
    } catch (error) {
      setDocumentView({ title, content: '', loading: false, error: error.response?.data?.detail || error.message })
    }
  }
  return (
    <>
      <PageHeader title="Graphify" question="Inspect and query real code-only repository graphs. Deterministic actions are zero-token; ⚡ actions create queue items only." actions={<ActionButton onClick={() => refresh(selectedId)} disabled={state.loading}>Refresh</ActionButton>} />
      {state.error && <div className="mb-3 rounded border border-clay/60 bg-clay/10 p-3 text-sm text-stone" role="alert">{state.error}</div>}
      {state.message && <div className="mb-3 rounded border border-olive/60 bg-olive/10 p-3 text-sm text-stone">{state.message}</div>}
      <div className="grid min-h-[70vh] gap-4 xl:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="rounded border border-softgraph bg-graphite/70 p-3">
          <div className="mb-2 text-xs uppercase tracking-wider text-champagne">Ingested repositories</div>
          <div className="space-y-2">{(data?.repos || []).map(repo => <button key={repo.id} onClick={() => setSelectedId(repo.id)} className={`w-full rounded border p-3 text-left ${repo.id === selectedId ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-ink'}`}><strong className="block text-sm text-stone">{repo.id}</strong><span className="mt-1 block text-xs text-taupe">{repo.node_count} nodes · {repo.commit_hash?.slice(0, 10)}</span></button>)}</div>
          {!state.loading && !(data?.repos || []).length && <EmptyState title="No repositories" detail="Use Repo Ingest to fetch one safely." />}
        </aside>
        <section className="min-w-0 rounded border border-softgraph bg-graphite/70 p-4">
          {!selected ? <EmptyState title="Select a repository" detail="A published repository graph will appear here." /> : <>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h2 className="text-lg font-semibold text-stone">{selected.id}</h2><p className="mt-1 text-xs text-taupe">{selected.node_count} nodes · {selected.edge_count} edges · commit {selected.commit_hash}</p></div>
              <div className="flex flex-wrap gap-2"><ActionButton onClick={() => operate('Rebuild', () => rebuildGraphifyRepository(selected.owner, selected.repository))} disabled={Boolean(state.operation)}>{state.operation === 'Rebuild' ? 'Rebuilding…' : 'Rebuild'}</ActionButton>{['semantic-extraction', 'community-naming', 'implementation-context'].map(work => <ActionButton key={work} kind="token" onClick={() => operate('Queue item', () => queueGraphifyModelWork(selected.owner, selected.repository, work))} disabled={Boolean(state.operation)}>⚡ {work.replace(/-/g, ' ')}</ActionButton>)}</div>
            </div>
            <div className="mt-4 grid gap-4 2xl:grid-cols-2">
              <div><div className="mb-2 text-xs uppercase tracking-wider text-champagne">Graph preview</div><iframe title={`${selected.id} graph preview`} src={selected.artifacts.graph} sandbox="allow-scripts" className="h-[520px] w-full rounded border border-softgraph bg-ink" data-testid="graphify-graph-preview" /></div>
              <div><div className="mb-2 text-xs uppercase tracking-wider text-champagne">Tree preview</div><iframe title={`${selected.id} tree preview`} src={selected.artifacts.tree} sandbox="allow-scripts" className="h-[520px] w-full rounded border border-softgraph bg-ink" data-testid="graphify-tree-preview" /></div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2" data-testid="graphify-artifact-links">
              {[['Report', 'report'], ['Provenance', 'provenance'], ['Receipt', 'receipt'], ['Graph JSON view', 'graph_json'], ['Quarantine scan', 'scan']].map(([label, key]) => <ActionButton key={key} onClick={() => showDocument(label, selected.artifacts[key])}>{label}</ActionButton>)}
              <a href={selected.artifacts.graph_json} className="rounded border border-softgraph bg-ink px-3 py-2 text-xs font-semibold text-stone hover:border-champagne/40">Download graph JSON</a>
            </div>
            {documentView.title && <div className="mt-4 rounded border border-softgraph bg-ink p-3"><div className="mb-2 text-xs uppercase text-champagne">{documentView.title}</div><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs text-stone">{documentView.loading ? 'Loading…' : documentView.error || documentView.content}</pre></div>}
            <div className="mt-4 rounded border border-softgraph bg-ink p-4">
              <div className="text-xs uppercase tracking-wider text-champagne">Deterministic graph actions · no model</div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <label className="text-xs text-taupe">Query<input value={actionInputs.query} onChange={event => setActionInputs(value => ({ ...value, query: event.target.value }))} className="mt-1 w-full rounded border border-softgraph bg-graphite p-2 text-stone" placeholder="Which modules handle signing?" /><ActionButton className="mt-2" onClick={() => runAction('query')} disabled={Boolean(state.operation)}>Run query</ActionButton></label>
                <label className="text-xs text-taupe">Explain node<input value={actionInputs.explain} onChange={event => setActionInputs(value => ({ ...value, explain: event.target.value }))} className="mt-1 w-full rounded border border-softgraph bg-graphite p-2 text-stone" placeholder="node name or id" /><ActionButton className="mt-2" onClick={() => runAction('explain')} disabled={Boolean(state.operation)}>Explain</ActionButton></label>
                <label className="text-xs text-taupe">Affected node<div className="flex gap-2"><input value={actionInputs.affected} onChange={event => setActionInputs(value => ({ ...value, affected: event.target.value }))} className="mt-1 min-w-0 flex-1 rounded border border-softgraph bg-graphite p-2 text-stone" placeholder="node name or id" /><input value={actionInputs.depth} onChange={event => setActionInputs(value => ({ ...value, depth: event.target.value }))} className="mt-1 w-16 rounded border border-softgraph bg-graphite p-2 text-stone" aria-label="Affected depth" /></div><ActionButton className="mt-2" onClick={() => runAction('affected')} disabled={Boolean(state.operation)}>Find affected</ActionButton></label>
                <label className="text-xs text-taupe">Shortest path<div className="flex gap-2"><input value={actionInputs.source} onChange={event => setActionInputs(value => ({ ...value, source: event.target.value }))} className="mt-1 min-w-0 flex-1 rounded border border-softgraph bg-graphite p-2 text-stone" placeholder="source" /><input value={actionInputs.target} onChange={event => setActionInputs(value => ({ ...value, target: event.target.value }))} className="mt-1 min-w-0 flex-1 rounded border border-softgraph bg-graphite p-2 text-stone" placeholder="target" /></div><ActionButton className="mt-2" onClick={() => runAction('path')} disabled={Boolean(state.operation)}>Find path</ActionButton></label>
              </div>
              {actionResult && <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded border border-softgraph bg-graphite p-3 text-xs text-stone">{actionResult.output || '(no output)'}</pre>}
            </div>
          </>}
        </section>
      </div>
    </>
  )
}

export function RepoIngest() {
  const [data, setData] = useState(null)
  const [url, setUrl] = useState('')
  const [operation, setOperation] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const validation = useMemo(() => validateGitHubRepositoryUrl(url), [url])
  const existing = validation.valid ? (data?.repos || []).find(repo => repo.id === validation.id) : null
  const displayed = result || existing
  const refresh = async () => { try { setData(await getDashboardRepoIngest()) } catch (requestError) { setError(requestError.message || 'Repo Ingest status unavailable.') } }
  useEffect(() => { refresh() }, [])
  const execute = async refetch => {
    if (!validation.valid) return
    setOperation(refetch ? 'Re-fetch' : 'Fetch')
    setError('')
    try {
      const response = await (refetch ? refetchGraphifyRepository(validation.normalized) : fetchGraphifyRepository(validation.normalized))
      setResult(response.repository)
      await refresh()
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message || `${refetch ? 'Re-fetch' : 'Fetch'} failed.`)
    } finally {
      setOperation('')
    }
  }
  return <><PageHeader title="Repo Ingest" question="Explicitly fetch a public GitHub repository through strict validation, safe shallow clone, quarantine scan, and code-only Graphify." />
    <div className="rounded border border-softgraph bg-graphite/70 p-5">
      <div className="grid gap-2 md:grid-cols-5">{(data?.steps || []).map((step, i) => <div key={step} className="rounded border border-softgraph bg-ink p-4 text-center"><div className="text-xs text-champagne">{i + 1}</div><div className="mt-1 text-sm font-semibold text-stone">{step}</div></div>)}</div>
      <label className="mt-5 block text-xs uppercase tracking-wider text-champagne">Public GitHub URL<input value={url} onChange={event => setUrl(event.target.value)} className="mt-2 w-full rounded border border-softgraph bg-ink px-3 py-3 text-sm text-stone outline-none focus:border-champagne" placeholder="https://github.com/owner/repository" autoComplete="off" spellCheck="false" /></label>
      <div className={`mt-2 text-xs ${validation.valid ? 'text-stone' : 'text-taupe'}`}>{url ? validation.valid ? `Validated locally: ${validation.normalized}` : validation.error : 'Typing validates locally only. Nothing is fetched until you click Fetch.'}</div>
      {existing && <div className="mt-3 rounded border border-champagne/50 bg-champagne/10 p-3 text-sm text-stone">Repository already exists at commit {existing.commit_hash}. Normal Fetch is disabled; use the explicit repository-specific Re-fetch button.</div>}
      {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-3 text-sm text-stone" role="alert">{error}</div>}
      <div className="mt-4 flex flex-wrap items-center gap-2"><ActionButton onClick={() => execute(false)} disabled={!validation.valid || Boolean(existing) || Boolean(operation)}>{operation === 'Fetch' ? 'Fetching, scanning, and Graphifying…' : 'Fetch'}</ActionButton>{existing && <ActionButton onClick={() => execute(true)} disabled={Boolean(operation)}>{operation === 'Re-fetch' ? `Re-fetching ${existing.id}…` : `Re-fetch ${existing.id}`}</ActionButton>}<span className="text-xs text-taupe">Current operation: {operation || 'idle'} · no model invocation</span></div>
    </div>
    {displayed && <section className="mt-4 rounded border border-olive/60 bg-graphite/70 p-5" data-testid="repo-ingest-success"><div className="flex items-center justify-between gap-3"><div><h2 className="text-lg font-semibold text-stone">Available: {displayed.id}</h2><p className="mt-1 text-xs text-taupe">Commit {displayed.commit_hash} · {displayed.node_count} nodes · Graphify {displayed.graphify_version}</p></div><StatusChip status="Ready" /></div><div className="mt-4 grid gap-3 md:grid-cols-4">{[['Files', displayed.scan_summary?.file_count], ['Directories', displayed.scan_summary?.directory_count], ['Bytes', displayed.scan_summary?.total_size], ['Scan', displayed.scan_summary?.validation_status]].map(([label, value]) => <div key={label} className="rounded border border-softgraph bg-ink p-3"><div className="text-xs uppercase text-champagne">{label}</div><div className="mt-1 text-sm text-stone">{value ?? 'unavailable'}</div></div>)}</div><div className="mt-4 flex flex-wrap gap-2">{[['Graph', 'graph'], ['Tree', 'tree'], ['Report', 'report'], ['Provenance', 'provenance'], ['Receipt', 'receipt'], ['Quarantine scan', 'scan']].map(([label, key]) => <a key={key} href={displayed.artifacts[key]} target="_blank" rel="noreferrer" className="rounded border border-softgraph bg-ink px-3 py-2 text-xs font-semibold text-stone hover:border-champagne/40">{label}</a>)}</div></section>}
    <div className="mt-4 rounded border border-softgraph bg-graphite/70 p-4 text-xs text-taupe"><p>{data?.note}</p><p className="mt-2">Canonical clones: {data?.canonical_roots?.clones || 'loading'}</p><p>Canonical outputs: {data?.canonical_roots?.outputs || 'loading'}</p><p>Canonical receipts: {data?.canonical_roots?.receipts || 'loading'}</p></div>
  </>
}

export function SettingsLaunchers() {
  const { data, loading, error } = useAsync(getHermesUiStatus)
  const { data: graphify } = useAsync(getDashboardGraphify)
  const { data: latitude } = useAsync(getLatitudeStatus)
  const [statusData, setStatusData] = useState(null)
  const [launching, setLaunching] = useState(false)
  const [refreshingStatus, setRefreshingStatus] = useState(false)
  const [showEmbedded, setShowEmbedded] = useState(false)
  const [iframeState, setIframeState] = useState('idle')
  const [copied, setCopied] = useState(false)
  const [copiedWorkbench, setCopiedWorkbench] = useState('')
  const status = statusData || data || {}
  useEffect(() => {
    if (data) setStatusData(data)
  }, [data])
  useEffect(() => {
    if (!showEmbedded) return undefined
    setIframeState('loading')
    const timer = setTimeout(() => setIframeState(current => current === 'loading' ? 'slow' : current), 8000)
    return () => clearTimeout(timer)
  }, [showEmbedded, status.iframe_url])
  const refreshStatus = async () => {
    setRefreshingStatus(true)
    try {
      const result = await getHermesUiStatus()
      setStatusData(result)
      if (!result?.embeddable) setShowEmbedded(false)
    } finally {
      setRefreshingStatus(false)
    }
  }
  const startHermes = async () => {
    setLaunching(true)
    try {
      const result = await launchHermesUi()
      setStatusData(result)
      if (!result?.embeddable) setShowEmbedded(false)
    } finally {
      setLaunching(false)
    }
  }
  const openHermes = () => {
    if (status?.http_reachable && status?.url) window.open(status.url, 'hermes_os')
  }
  const toggleEmbedded = () => {
    if (status?.http_reachable && status?.embeddable) setShowEmbedded(value => !value)
  }
  const copyCommand = async () => {
    await navigator.clipboard?.writeText(status.launch_command || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }
  const copyWorkbench = async target => {
    await navigator.clipboard?.writeText(launcherPrompt(target))
    setCopiedWorkbench(target)
    setTimeout(() => setCopiedWorkbench(''), 1400)
  }
  return (
    <>
      <PageHeader title="Settings / Launchers" question="Local launch commands and dashboard preferences." />
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded border border-softgraph bg-graphite/70 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-wider text-champagne">Hermes UI</div>
              <div className="mt-1 text-sm font-semibold text-ivory">{loading ? 'checking' : status.state || error || 'unavailable'}</div>
            </div>
            <div className={`rounded px-2 py-1 text-[11px] font-mono ${status.http_reachable ? 'bg-olive/20 text-stone' : status.supported === false ? 'bg-clay/20 text-stone' : 'bg-softgraph text-taupe'}`}>
              {status.http_reachable ? (status.embeddable ? 'RUNNING EMBEDDED' : 'WINDOW ONLY') : status.supported === false ? 'UNSUPPORTED' : launching ? 'STARTING' : 'NOT RUNNING'}
            </div>
          </div>
          <div className="mt-4 grid gap-2 text-xs text-taupe">
            <div><span className="text-stone">Target:</span> {status.url || 'http://127.0.0.1:8081'}</div>
            <div><span className="text-stone">Runtime:</span> {status.runtime || 'AgenticOSClean'} / {status.user || 'liam'}</div>
            <div><span className="text-stone">Version:</span> {status.version || 'unavailable'}</div>
            <div><span className="text-stone">Installed:</span> {status.installed ? 'yes' : 'no'}</div>
            <div><span className="text-stone">Process:</span> {status.process_running ? 'running' : 'not running'}</div>
            <div><span className="text-stone">HTTP:</span> {status.http_reachable ? 'reachable' : 'not reachable'}</div>
            <div><span className="text-stone">Embeddable:</span> {status.embeddable ? 'yes' : 'no'}</div>
            {status.blocking_header && <div><span className="text-stone">Blocking header:</span> {status.blocking_header}</div>}
            {status.reason && <div><span className="text-stone">Reason:</span> {status.reason}</div>}
            {status.last_error && <div><span className="text-stone">Last error:</span> {status.last_error}</div>}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <ActionButton onClick={startHermes} disabled={launching || status.supported === false}>{launching ? 'Starting' : 'Start Hermes UI'}</ActionButton>
            <ActionButton onClick={openHermes} disabled={!status.http_reachable}>Open Hermes UI</ActionButton>
            <ActionButton onClick={toggleEmbedded} disabled={!status.http_reachable || !status.embeddable}>{showEmbedded ? 'Hide embedded Hermes' : 'Show embedded Hermes'}</ActionButton>
            <ActionButton onClick={refreshStatus} disabled={refreshingStatus}>{refreshingStatus ? 'Refreshing' : 'Refresh status'}</ActionButton>
            <ActionButton onClick={copyCommand} disabled={!status.launch_command}>{copied ? 'Copied' : 'Copy launch command'}</ActionButton>
          </div>
          <code className="mt-3 block whitespace-pre-wrap break-words rounded border border-softgraph bg-ink p-3 text-xs text-stone">{status.launch_command || 'Launcher command unavailable.'}</code>
          {status.http_reachable && !status.embeddable && (
            <div className="mt-3 rounded border border-champagne/40 bg-ink p-3 text-xs text-stone">
              Hermes UI is running, but its current security headers prevent embedding. Use Open Hermes UI.
            </div>
          )}
        </div>
        <EmptyState title="Telegram instructions" detail="Instructions only. Use the established client or internal bridge outside this surface; no message or bridge action is exposed here." />
      </div>
      <section className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="launcher-status-grid">
        <div className="rounded border border-softgraph bg-graphite/70 p-4" data-launcher="graphify"><div className="flex justify-between gap-2"><h2 className="font-semibold text-stone">Graphify</h2><StatusChip status={graphify?.installed ? 'Ready' : 'Unavailable'} /></div><p className="mt-2 text-xs text-taupe">{graphify?.status || 'Status unavailable'}.</p><p className="mt-1 text-xs text-taupe">Data inspected: {graphify?.data_inspected ? 'yes' : 'no'}</p></div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4" data-launcher="latitude"><div className="flex justify-between gap-2"><h2 className="font-semibold text-stone">Latitude</h2><StatusChip status={latitude?.connected ? 'Ready' : latitude?.configured ? 'Needs Me' : 'Unavailable'} /></div><p className="mt-2 text-xs text-taupe">Additive observability: {latitude?.connected ? 'connected' : latitude?.configured ? 'configured / degraded' : 'not configured'}.</p><p className="mt-1 text-xs text-taupe">{latitude?.degraded_reason || 'No expanded trace payload shown.'}</p></div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4" data-launcher="agentmail"><div className="flex justify-between gap-2"><h2 className="font-semibold text-stone">AgentMail</h2><StatusChip status="Ready">internal-live</StatusChip></div><p className="mt-2 text-xs text-taupe">Status only: olmec1@agentmail.to → liam@timetorevenue.com.</p><p className="mt-1 text-xs text-taupe">No send control on this surface.</p></div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4" data-launcher="telegram"><div className="flex justify-between gap-2"><h2 className="font-semibold text-stone">Telegram</h2><StatusChip status="Unavailable">instructions only</StatusChip></div><p className="mt-2 text-xs text-taupe">Use the established client/bridge outside this surface. No bridge edit or message control.</p></div>
        {['codex', 'claude-code'].map(target => <div key={target} className="rounded border border-softgraph bg-graphite/70 p-4" data-launcher={target}><div className="flex justify-between gap-2"><h2 className="font-semibold text-stone">{target === 'codex' ? 'Codex' : 'Claude Code'}</h2><StatusChip status="Ready">copy prompt</StatusChip></div><p className="mt-2 text-xs text-taupe">Canonical Linux launch and exact scoped permission header.</p><ActionButton className="mt-3" onClick={() => copyWorkbench(target)}>{copiedWorkbench === target ? 'Copied' : 'Copy prompt'}</ActionButton></div>)}
      </section>
      {showEmbedded && status.http_reachable && status.embeddable && (
        <section className="mt-4 rounded border border-softgraph bg-graphite/70 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-sm font-semibold text-stone">Embedded Hermes</div>
            <div className="text-xs text-taupe">{iframeState === 'loading' ? 'Loading' : iframeState === 'slow' ? 'Still loading' : 'Running'}</div>
          </div>
          {iframeState === 'slow' && <div className="mb-2 rounded border border-champagne/40 bg-ink p-2 text-xs text-stone">Hermes is reachable, but the embedded view has not completed loading. Open in window remains available.</div>}
          <iframe
            title="Hermes UI"
            src={status.iframe_url || status.url || 'http://127.0.0.1:8081'}
            onLoad={() => setIframeState('loaded')}
            className="h-[72vh] w-full rounded border border-softgraph bg-ink"
          />
        </section>
      )}
    </>
  )
}
