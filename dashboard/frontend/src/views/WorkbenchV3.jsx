import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, Bot, CheckCircle2, FileUp, Play, Save, SlidersHorizontal, X } from 'lucide-react'
import { askHermesMessage, createQueueChain, createQueueItem, getDashboardAgents, getDashboardResults, getDashboardSystemWatch, routeMessageBoardCommand } from '../api'
import { ActionButton, EmptyState, PageHeader, RowButton, SourceChip, StatusChip } from '../components/DashboardKit'

const csv = value => Array.isArray(value) ? value.filter(Boolean).join(',') : String(value || '')
const entryId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`
const errorText = error => {
  const detail = error?.response?.data?.detail
  const value = detail?.output || detail || error?.message || 'Action failed'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function WorkOrderCard({ card, busy, error, editing, editDraft, onAction, onCancel, onEditChange, onEditApply, onEditCancel }) {
  if (!card) return null
  const order = card.work_order
  if (!order) {
    return (
      <div className="rounded border border-champagne/50 bg-graphite p-4">
        <div className="flex items-center gap-2 text-champagne"><AlertCircle size={16} /><span className="font-semibold">No deterministic route matched.</span></div>
        <p className="mt-2 text-sm text-taupe">Nothing was created. Ask Hermes to triage only if you want to spend model tokens.</p>
        {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay">{error}</div>}
        <div className="mt-4 flex flex-wrap gap-2">
          <ActionButton kind="token" onClick={() => onAction('hermes')} disabled={Boolean(busy)}>{busy ? 'Asking Hermes' : <><Bot size={13} />Ask Hermes to triage</>}</ActionButton>
          <ActionButton onClick={onCancel} disabled={Boolean(busy)}><X size={13} />Cancel</ActionButton>
        </div>
      </div>
    )
  }
  if (editing) {
    return (
      <div className="rounded border border-champagne/50 bg-graphite p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs font-mono text-champagne">Edit route/model confirmation</div>
            <h3 className="mt-1 text-base font-semibold text-ivory">{order.title}</h3>
          </div>
          <StatusChip status="Ready">local only</StatusChip>
        </div>
        <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
          {[
            ['workflow', 'Workflow'],
            ['owner', 'Owner'],
            ['workbench', 'Workbench'],
            ['priority', 'Priority'],
          ].map(([key, label]) => (
            <label key={key} className="block">
              <span className="text-xs text-taupe">{label}</span>
              <input value={editDraft?.[key] || ''} onChange={event => onEditChange(key, event.target.value)} className="mt-1 h-9 w-full rounded border border-softgraph bg-ink px-2 text-xs text-stone outline-none focus:border-champagne/60" />
            </label>
          ))}
        </div>
        <div className="mt-3 rounded border border-softgraph bg-ink p-3 text-xs text-taupe">
          This changes only this confirmation card before queue creation. It does not mutate command_routes.json or call Hermes.
        </div>
        {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay">{error}</div>}
        <div className="mt-4 flex flex-wrap gap-2">
          <ActionButton kind="primary" onClick={onEditApply}>Apply changes</ActionButton>
          <ActionButton onClick={onEditCancel}>Cancel edit</ActionButton>
        </div>
      </div>
    )
  }
  return (
    <div className="rounded border border-champagne/50 bg-graphite p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-xs font-mono text-champagne">{order.workflow}</div>
          <h3 className="mt-1 text-base font-semibold text-ivory">{order.title}</h3>
        </div>
        <StatusChip status="Ready">{card.confidence}</StatusChip>
      </div>
      <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
        <div><span className="text-taupe">Owner</span><div className="text-stone">{order.owner}</div></div>
        <div><span className="text-taupe">Priority</span><div className="text-stone">{order.priority}</div></div>
        <div><span className="text-taupe">Source</span><div className="text-stone">{order.source}</div></div>
        <div><span className="text-taupe">Workbench</span><div className="text-stone">{order.workbench || 'lane'}</div></div>
        <div><span className="text-taupe">Tags</span><div className="text-stone">{csv(order.tags)}</div></div>
        <div><span className="text-taupe">Attachments</span><div className="text-stone">{csv(order.source_refs) || 'None'}</div></div>
      </div>
      <div className="mt-3 rounded border border-softgraph bg-ink p-3 text-sm text-stone">
        <div className="text-[11px] uppercase tracking-wide text-taupe">Definition of Done</div>
        <div className="mt-1 whitespace-pre-wrap">{order.definition_of_done || 'Unavailable from workflow contract.'}</div>
      </div>
      <div className="mt-3 grid gap-3 text-xs md:grid-cols-2">
        <pre className="whitespace-pre-wrap rounded border border-softgraph bg-ink p-3 text-taupe">Allowed actions{'\n'}{csv(order.allowed_actions)}</pre>
        <pre className="whitespace-pre-wrap rounded border border-softgraph bg-ink p-3 text-taupe">Stop conditions{'\n'}{csv(order.stop_conditions)}</pre>
      </div>
      {order.steps?.length > 0 && <div className="mt-3 rounded border border-softgraph bg-ink p-3 text-xs text-taupe">Step progress starts at 0 of {order.steps.length}.</div>}
      <div className="mt-3 text-xs font-mono text-champagne">{card.token_usage_text}</div>
      {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay">{error}</div>}
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton kind="primary" onClick={() => onAction('run')} disabled={Boolean(busy)}><Play size={13} />{busy === 'run' ? 'Creating' : 'Run'}</ActionButton>
        <ActionButton onClick={() => onAction('edit')} disabled={Boolean(busy)}><SlidersHorizontal size={13} />Edit route/model</ActionButton>
        <ActionButton kind="token" onClick={() => onAction('hermes')} disabled={Boolean(busy)}><Bot size={13} />{busy === 'hermes' ? 'Asking Hermes' : 'Ask Hermes to triage'}</ActionButton>
        <ActionButton onClick={() => onAction('save')} disabled={Boolean(busy)}><Save size={13} />{busy === 'save' ? 'Saving' : 'Save to queue only'}</ActionButton>
        <ActionButton onClick={onCancel} disabled={Boolean(busy)}><X size={13} />Cancel</ActionButton>
      </div>
    </div>
  )
}

function ChainProposalCard({ proposal, draft, busy, error, onDraftChange, onConfirm, onCancel }) {
  const value = draft || JSON.stringify(proposal, null, 2)
  return (
    <div className="rounded border border-champagne/50 bg-graphite p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-xs font-mono text-champagne">Hermes chain proposal</div>
          <h3 className="mt-1 text-base font-semibold text-ivory">{proposal.title}</h3>
        </div>
        <StatusChip status="Ready">{proposal.steps?.length || 0} steps</StatusChip>
      </div>
      <textarea value={value} onChange={event => onDraftChange(event.target.value)} className="mt-3 min-h-72 w-full rounded border border-softgraph bg-ink px-3 py-2 font-mono text-xs text-stone outline-none focus:border-champagne/60" />
      {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay">{error}</div>}
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton kind="primary" onClick={() => onConfirm(value)} disabled={Boolean(busy)}><CheckCircle2 size={13} />{busy ? 'Filing' : 'Confirm chain'}</ActionButton>
        <ActionButton onClick={onCancel} disabled={Boolean(busy)}><X size={13} />Cancel</ActionButton>
      </div>
    </div>
  )
}

export function MessageBoard({ refresh }) {
  const [text, setText] = useState('')
  const [files, setFiles] = useState([])
  const [thread, setThread] = useState([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [cardBusy, setCardBusy] = useState({})
  const [cardErrors, setCardErrors] = useState({})
  const [editingCard, setEditingCard] = useState(null)
  const [editDraft, setEditDraft] = useState({})
  const [chainDrafts, setChainDrafts] = useState({})

  const sourceRefs = files.map(file => `attachment:${file.name}`)
  const submit = async event => {
    event.preventDefault()
    const clean = text.trim()
    if (!clean) return
    setBusy(true)
    setMessage('')
    const userEntry = { id: entryId(), type: 'user', text: clean, source_refs: sourceRefs }
    try {
      const card = await routeMessageBoardCommand({ text: clean, source_refs: sourceRefs })
      setThread(current => [...current, userEntry, { id: entryId(), type: 'card', card, prompt: clean }])
      setText('')
    } catch (error) {
      setThread(current => [...current, userEntry, { id: entryId(), type: 'error', text: errorText(error) || 'Route failed' }])
    } finally {
      setBusy(false)
    }
  }

  const clearCardError = cardId => setCardErrors(current => {
    const next = { ...current }
    delete next[cardId]
    return next
  })

  const setCardError = (cardId, text) => setCardErrors(current => ({ ...current, [cardId]: text }))

  const removeCard = cardId => {
    setThread(current => current.filter(item => item.id !== cardId))
    clearCardError(cardId)
    setCardBusy(current => {
      const next = { ...current }
      delete next[cardId]
      return next
    })
    if (editingCard === cardId) {
      setEditingCard(null)
      setEditDraft({})
    }
  }

  const startEdit = (cardId, order) => {
    setEditingCard(cardId)
    setEditDraft({
      workflow: order.workflow || '',
      owner: order.owner || '',
      workbench: order.workbench || '',
      priority: order.priority || '',
    })
    clearCardError(cardId)
  }

  const applyEdit = cardId => {
    setThread(current => current.map(entry => {
      if (entry.id !== cardId || !entry.card?.work_order) return entry
      const workOrder = {
        ...entry.card.work_order,
        workflow: editDraft.workflow,
        owner: editDraft.owner,
        workbench: editDraft.workbench,
        priority: editDraft.priority,
      }
      return { ...entry, card: { ...entry.card, work_order: workOrder } }
    }))
    setEditingCard(null)
    setEditDraft({})
  }

  const createFromCard = async (cardEntry, mode) => {
    const cardId = cardEntry.id
    if (cardBusy[cardId]) return
    clearCardError(cardId)
    if (!cardEntry.card?.work_order) {
      if (mode === 'hermes') {
        setCardBusy(current => ({ ...current, [cardId]: 'hermes' }))
        try {
          const reply = await askHermesMessage(cardEntry.prompt || '', cardEntry.card?.work_order?.source_refs || [])
          const chainId = entryId()
          setThread(current => [...current, reply.chain_proposal ? { id: chainId, type: 'chain', proposal: reply.chain_proposal, token: reply.token_usage_text || 'Token usage: unavailable from current CLI output' } : { id: entryId(), type: 'hermes', text: reply.reply || reply.answer || reply.output || 'Hermes replied.', token: reply.token_usage_text || 'Token usage: unavailable from current CLI output', needsInput: reply.needs_input_item }])
          if (reply.chain_proposal) setChainDrafts(current => ({ ...current, [chainId]: JSON.stringify(reply.chain_proposal, null, 2) }))
        } catch (error) {
          setCardError(cardId, errorText(error) || 'Hermes unavailable')
        } finally {
          setCardBusy(current => ({ ...current, [cardId]: null }))
        }
      }
      return
    }
    if (mode === 'hermes') {
      setCardBusy(current => ({ ...current, [cardId]: 'hermes' }))
      try {
        const reply = await askHermesMessage(cardEntry.card.work_order.context, cardEntry.card.work_order.source_refs || [])
        const chainId = entryId()
        setThread(current => [...current, reply.chain_proposal ? { id: chainId, type: 'chain', proposal: reply.chain_proposal, token: reply.token_usage_text || 'Token usage: unavailable from current CLI output' } : { id: entryId(), type: 'hermes', text: reply.reply || reply.answer || reply.output || 'Hermes replied.', token: reply.token_usage_text || 'Token usage: unavailable from current CLI output', needsInput: reply.needs_input_item }])
        if (reply.chain_proposal) setChainDrafts(current => ({ ...current, [chainId]: JSON.stringify(reply.chain_proposal, null, 2) }))
      } catch (error) {
        setCardError(cardId, errorText(error) || 'Hermes unavailable')
      } finally {
        setCardBusy(current => ({ ...current, [cardId]: null }))
      }
      return
    }
    if (mode === 'edit') {
      startEdit(cardId, cardEntry.card.work_order)
      return
    }
    setCardBusy(current => ({ ...current, [cardId]: mode }))
    try {
      const order = cardEntry.card.work_order
      const result = await createQueueItem({
        title: order.title,
        owner: order.owner,
        priority: order.priority,
        tags: csv(order.tags),
        source: 'message_board',
        context: order.context,
        source_refs: csv(order.source_refs),
        allowed_actions: csv(order.allowed_actions),
        stop_conditions: csv(order.stop_conditions),
        definition_of_done: order.definition_of_done,
        workbench: order.workbench,
        step_index: order.steps?.length ? 0 : null,
      })
      const itemId = result.item?.id
      if (!itemId) throw new Error('Queue item create succeeded without an item id')
      setMessage(`${mode === 'run' ? 'Queued to run' : 'Saved'} ${itemId}`)
      setThread(current => current.map(entry => entry.id === cardId ? { id: entryId(), type: 'created', item: result.item, mode } : entry))
      setFiles([])
      refresh?.()
    } catch (error) {
      setCardError(cardId, errorText(error))
    } finally {
      setCardBusy(current => ({ ...current, [cardId]: null }))
    }
  }

  const confirmChain = async (entry, raw) => {
    if (cardBusy[entry.id]) return
    setCardBusy(current => ({ ...current, [entry.id]: 'chain' }))
    clearCardError(entry.id)
    try {
      const payload = JSON.parse(raw)
      const result = await createQueueChain(payload)
      setThread(current => current.map(row => row.id === entry.id ? { id: entryId(), type: 'created', item: result.parent, mode: 'chain', steps: result.steps } : row))
      refresh?.()
    } catch (error) {
      setCardError(entry.id, errorText(error))
    } finally {
      setCardBusy(current => ({ ...current, [entry.id]: null }))
    }
  }

  return (
    <>
      <PageHeader title="Message Board" question="Command intake is deterministic by default; Hermes triage only runs on click." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="min-h-[62vh] rounded border border-softgraph bg-graphite/70 p-4">
          <div className="space-y-3">
            {thread.map(entry => (
              <div key={entry.id} className={entry.type === 'user' ? 'rounded border border-softgraph bg-ink p-3 text-stone' : ''}>
                {entry.type === 'user' && <><div className="text-sm">{entry.text}</div>{entry.source_refs?.length > 0 && <div className="mt-2 text-xs text-taupe">{csv(entry.source_refs)}</div>}</>}
                {entry.type === 'card' && <WorkOrderCard card={entry.card} busy={cardBusy[entry.id]} error={cardErrors[entry.id]} editing={editingCard === entry.id} editDraft={editDraft} onAction={mode => createFromCard(entry, mode)} onCancel={() => removeCard(entry.id)} onEditChange={(key, value) => setEditDraft(current => ({ ...current, [key]: value }))} onEditApply={() => applyEdit(entry.id)} onEditCancel={() => { setEditingCard(null); setEditDraft({}) }} />}
                {entry.type === 'chain' && <ChainProposalCard proposal={entry.proposal} draft={chainDrafts[entry.id]} busy={cardBusy[entry.id]} error={cardErrors[entry.id]} onDraftChange={value => setChainDrafts(current => ({ ...current, [entry.id]: value }))} onConfirm={raw => confirmChain(entry, raw)} onCancel={() => removeCard(entry.id)} />}
                {entry.type === 'hermes' && <div className="rounded border border-champagne/40 bg-ink p-3"><div className="whitespace-pre-wrap text-sm text-stone">{entry.text}</div>{entry.needsInput?.id && <div className="mt-2 text-xs text-champagne">Needs input: {entry.needsInput.id}</div>}<div className="mt-2 text-xs font-mono text-champagne">{entry.token}</div></div>}
                {entry.type === 'created' && <div className="rounded border border-olive/50 bg-olive/10 p-3 text-sm text-stone"><CheckCircle2 size={14} className="mr-2 inline text-olive" />{entry.mode === 'chain' ? 'Chain filed' : entry.mode === 'run' ? 'Queued to run' : 'Saved to queue'}: {entry.item?.id}{entry.steps?.length ? ` (${entry.steps.length} steps)` : ''}</div>}
                {entry.type === 'error' && <div className="rounded border border-clay/60 bg-clay/10 p-3 text-sm text-clay">{entry.text}</div>}
              </div>
            ))}
            {!thread.length && <EmptyState title="No messages yet" detail="Submit a command to produce a confirmation card before any queue mutation." />}
          </div>
        </section>
        <form onSubmit={submit} className="rounded border border-softgraph bg-graphite/70 p-4">
          <textarea value={text} onChange={event => setText(event.target.value)} placeholder="Type an operator command" className="min-h-40 w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none placeholder:text-taupe" />
          <label className="mt-3 flex cursor-pointer items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 text-xs text-stone hover:border-champagne/50">
            <FileUp size={14} />
            Attach file
            <input type="file" multiple className="hidden" onChange={event => setFiles(Array.from(event.target.files || []))} />
          </label>
          {files.length > 0 && <div className="mt-2 text-xs text-taupe">{files.map(file => file.name).join(', ')}</div>}
          <ActionButton kind="primary" type="submit" className="mt-3 w-full" disabled={busy}>{busy ? 'Working' : 'Submit'}</ActionButton>
          {message && <div className="mt-3 text-xs text-champagne">{message}</div>}
        </form>
      </div>
    </>
  )
}

export function AgentsPage() {
  const [data, setData] = useState(null)
  const [selected, setSelected] = useState(null)
  useEffect(() => { getDashboardAgents().then(setData) }, [])
  const components = data?.components || []
  const current = selected || components[0]
  return (
    <>
      <PageHeader title="Agents" question="Local component drilldowns by owner, workbench, receipts, and token attribution." />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {components.map(component => <button key={component.id} onClick={() => setSelected(component)} className="rounded border border-softgraph bg-graphite/70 p-3 text-left hover:border-champagne/50"><div className="text-sm font-semibold text-stone">{component.name}</div><div className="mt-1 text-xs text-taupe">{component.group}</div><div className="mt-2 text-xs text-champagne">{component.tokens.tokens ? `${component.tokens.tokens.toLocaleString()} tokens` : 'Token usage: unavailable from current CLI output'}</div></button>)}
      </div>
      {current && <section className="mt-4 rounded border border-softgraph bg-graphite/70 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold text-ivory">{current.name}</h2><span className="text-xs text-taupe">{current.status_text}</span></div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {['queued', 'running', 'done'].map(key => <div key={key} className="rounded border border-softgraph bg-ink p-3"><div className="text-xs uppercase text-taupe">{key}</div><div className="mt-1 text-2xl text-stone">{current.counts[key]}</div></div>)}
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div className="space-y-2">{current.items.map(item => <RowButton key={item.id} title={item.title} meta={`${item.id} · ${item.owner} · ${item.workbench || 'no workbench'}`} right={<><SourceChip source={item.source} /><StatusChip status={item.honest_status || item.status} /></>} />)}{!current.items.length && <EmptyState title="No queue items" detail="Nothing matched this component." />}</div>
          <div className="space-y-2">{current.receipts.map(receipt => <div key={receipt.path} className="rounded border border-softgraph bg-ink p-3 text-xs text-taupe">{receipt.path}</div>)}{!current.receipts.length && <EmptyState title="No receipts" detail="No attributable receipts found by local filename match." />}</div>
        </div>
      </section>}
    </>
  )
}

export function ArtifactsPage() {
  const [data, setData] = useState(null)
  useEffect(() => { getDashboardResults().then(setData) }, [])
  return (
    <>
      <PageHeader title="Artifacts" question="Receipts, outputs, packets, and local logs." />
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{(data?.items || []).map(item => <RowButton key={item.path} title={item.title} meta={`${item.source} · ${item.path}`} right={<SourceChip source={item.source} />} />)}</div>
    </>
  )
}

export function MissionControl() {
  const [watch, setWatch] = useState(null)
  useEffect(() => { getDashboardSystemWatch().then(setWatch) }, [])
  const stalled = watch?.stalled || []
  const backup = watch?.backup || {}
  const latestBackup = backup?.latest
  return (
    <>
      <PageHeader title="Mission Control" question="Read-only system watch: backend, queue tooling, stalled runs, and log tail." />
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded border border-softgraph bg-graphite/70 p-4"><div className="text-xs text-taupe">Backend</div><div className="mt-1 text-lg text-stone">{watch?.backend?.status || 'loading'}</div></div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4"><div className="text-xs text-taupe">Queue Tooling</div><div className="mt-1 text-lg text-stone">{watch?.queue_tooling?.status || 'loading'}</div></div>
        <div className="rounded border border-softgraph bg-graphite/70 p-4"><div className="text-xs text-taupe">Stalled Runs</div><div className="mt-1 text-lg text-stone">{stalled.length}</div></div>
      </div>
      <section className={`mt-4 rounded border p-4 ${backup?.needs_attention ? 'border-clay/70 bg-clay/10' : 'border-softgraph bg-graphite/70'}`}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-stone">Automated Backup</h2>
            <div className="mt-1 text-xs text-taupe">{backup?.token_usage_text || 'Token usage: no agent invocation'}</div>
          </div>
          <StatusChip status={backup?.needs_attention ? 'Blocked' : 'Done'}>{backup?.state || 'loading'}</StatusChip>
        </div>
        <div className="mt-3 grid gap-2 text-xs text-taupe md:grid-cols-2">
          <div><span className="text-stone">Last:</span> {latestBackup?.ts || 'no backup receipts yet'}</div>
          <div><span className="text-stone">Target:</span> {latestBackup?.target || 'D:\\TTROS_Backups'}</div>
          <div className="md:col-span-2"><span className="text-stone">Snapshot:</span> {latestBackup?.snapshot_path || 'unavailable'}</div>
          <div className="md:col-span-2"><span className="text-stone">Receipt:</span> {backup?.latest_receipt_path || 'queue/receipts/backups.jsonl'}</div>
          <div className="md:col-span-2"><span className="text-stone">Log:</span> {backup?.latest_log_path || 'unavailable'}</div>
        </div>
      </section>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div className="rounded border border-softgraph bg-graphite/70 p-4"><h2 className="text-sm font-semibold text-stone">Stalled</h2><div className="mt-3 space-y-2">{stalled.map(item => <RowButton key={item.id} title={item.title} meta={`${item.id} · ${item.stalled_minutes} min`} right={<StatusChip status="Blocked">stalled</StatusChip>} />)}{!stalled.length && <EmptyState title="No stalled runs" detail="No claimed/running queue item exceeded the configured window." />}</div></div>
        <pre className="max-h-96 overflow-auto rounded border border-softgraph bg-ink p-3 text-xs text-taupe">{(watch?.error_log_tail || []).join('\n') || 'No log tail available.'}</pre>
      </div>
    </>
  )
}
