import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Clipboard, FileText, ListChecks, Plus, RefreshCw } from 'lucide-react'
import { createQueueItem, getQueueItems, getQueueNext, getQueuePrompt, getQueueReceipt, getQueueStatus } from '../api'

const QUEUE_STATUSES = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled']
const QUEUE_OWNERS = ['unassigned', 'hermes', 'codex', 'claude', 'revenue', 'marketing', 'delivery', 'operations']
const QUEUE_PRIORITIES = ['low', 'normal', 'high', 'urgent']

const formatStatus = value => String(value || '').replace(/_/g, ' ')

const compactReason = value => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return 'Local queue endpoint did not return a reason.'
  return text.length > 180 ? `${text.slice(0, 177).trim()}...` : text
}

const renderList = value => {
  const items = Array.isArray(value) ? value : []
  return items.length ? items.join('\n') : ''
}

const compactOutput = value => {
  const text = String(value || '').trim()
  if (!text) return 'None'
  return text.length > 1600 ? `${text.slice(0, 1597).trim()}...` : text
}

const tokenUsageText = lines => {
  const clean = Array.isArray(lines) ? lines.filter(Boolean) : []
  return clean.length ? clean.join('\n') : 'Token usage: unavailable from current CLI output.'
}

const timestampValue = value => {
  if (!value) return 0
  const time = Date.parse(value)
  return Number.isNaN(time) ? 0 : time
}

const idValue = value => {
  const match = String(value || '').match(/(\d+)(?!.*\d)/)
  return match ? Number.parseInt(match[1], 10) : 0
}

const sortQueueItemsNewestFirst = list => [...list].sort((left, right) => {
  const leftUpdated = timestampValue(left.updated_at)
  const rightUpdated = timestampValue(right.updated_at)
  if (rightUpdated !== leftUpdated) return rightUpdated - leftUpdated

  const leftCreated = timestampValue(left.created_at)
  const rightCreated = timestampValue(right.created_at)
  if (rightCreated !== leftCreated) return rightCreated - leftCreated

  const rightId = idValue(right.id)
  const leftId = idValue(left.id)
  if (rightId !== leftId) return rightId - leftId

  return String(right.id || '').localeCompare(String(left.id || ''))
})

const receiptLabel = receipt => {
  if (!receipt) return 'Receipt unavailable'
  if (typeof receipt === 'string') return receipt
  return receipt.path || receipt.id || 'Receipt path unavailable'
}

const REVIEW_OR_COMPLETE_STATUSES = new Set(['human_review', 'done', 'blocked', 'needs_input'])

const emptyCreateForm = {
  title: '',
  owner: 'unassigned',
  priority: 'normal',
  tags: '',
  context: '',
}

const copyToClipboard = async text => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const node = document.createElement('textarea')
  node.value = text
  node.setAttribute('readonly', '')
  node.style.position = 'fixed'
  node.style.top = '-1000px'
  document.body.appendChild(node)
  node.select()
  document.execCommand('copy')
  document.body.removeChild(node)
}

const DetailRow = ({ label, value }) => (
  <div>
    <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">{label}</div>
    <div className="mt-1 whitespace-pre-wrap break-words text-sm text-stone">{value || 'None'}</div>
  </div>
)

const PromptButton = ({ target, busy, onCopy }) => (
  <button
    type="button"
    onClick={() => onCopy(target)}
    disabled={busy}
    className="inline-flex items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone transition-colors hover:border-champagne hover:text-ivory disabled:cursor-not-allowed disabled:opacity-60"
  >
    <Clipboard size={13} />
    {busy ? `Copying ${target}...` : `Copy ${target[0].toUpperCase()}${target.slice(1)} prompt`}
  </button>
)

const CountTile = ({ label, value }) => (
  <div className="rounded border border-softgraph bg-ink px-3 py-3">
    <div className="truncate text-[10px] font-mono uppercase text-taupe">{formatStatus(label)}</div>
    <div className="mt-1 font-mono text-lg text-stone">{value ?? 0}</div>
  </div>
)

const fieldBase =
  'mt-1 w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none transition-colors placeholder:text-taupe focus:border-champagne'

const FieldLabel = ({ label, children }) => (
  <label className="block">
    <span className="text-[11px] font-semibold uppercase tracking-wider text-taupe">{label}</span>
    {children}
  </label>
)

export default function Queue() {
  const [status, setStatus] = useState(null)
  const [items, setItems] = useState([])
  const [nextItem, setNextItem] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [createState, setCreateState] = useState({ submitting: false, message: '', error: null })
  const [promptCopy, setPromptCopy] = useState({ target: null, message: '', error: null })
  const [runState, setRunState] = useState({ running: false, result: null, error: null })
  const [selectedReceiptPath, setSelectedReceiptPath] = useState('')
  const [receiptState, setReceiptState] = useState({ loading: false, content: '', error: null })
  const [artifactState, setArtifactState] = useState({ path: '', loading: false, artifact: null, error: null })
  const [state, setState] = useState({ loading: true, error: null })

  const selected = useMemo(
    () => items.find(item => item.id === selectedId) || null,
    [items, selectedId],
  )
  const selectedStatus = selected?.status || ''
  const latestReceipt = selected?.latest_receipt || (selected?.receipts?.length ? selected.receipts[selected.receipts.length - 1] : null)
  const hasReceipt = Boolean(receiptLabel(latestReceipt) && latestReceipt && receiptLabel(latestReceipt) !== 'Receipt path unavailable')
  const runArtifacts = Array.isArray(selected?.run_artifacts) ? selected.run_artifacts : []
  const hasProducedArtifact = selectedStatus === 'human_review' && runArtifacts.some(artifact => artifact.available && artifact.path !== receiptLabel(latestReceipt))
  const isReviewOrComplete = REVIEW_OR_COMPLETE_STATUSES.has(selectedStatus)
  const isWorkerRunning = selectedStatus === 'agent_working'
  const showPersistedRunState = Boolean(selected && (hasReceipt || isReviewOrComplete || isWorkerRunning) && !runState.result && !runState.error && !runState.running)
  const runButtonLabel = isWorkerRunning
    ? 'Worker running / refresh for status'
    : hasReceipt || isReviewOrComplete
      ? 'Rerun assigned worker'
      : 'Run assigned worker'

  const refreshQueue = async (preferredId = selectedId) => {
    setState({ loading: true, error: null })
    try {
      const [statusData, itemsData, nextData] = await Promise.all([getQueueStatus(), getQueueItems(), getQueueNext()])
      if (statusData?.success === false || itemsData?.success === false || nextData?.success === false) {
        throw new Error(statusData?.reason || itemsData?.reason || nextData?.reason || 'Queue unavailable')
      }

      const list = sortQueueItemsNewestFirst(itemsData?.items || [])
      const next = nextData?.item || null
      const preferredExists = preferredId && list.some(item => item.id === preferredId)
      setStatus(statusData)
      setItems(list)
      setNextItem(next)
      setSelectedId(preferredExists ? preferredId : next?.id || list[0]?.id || null)
      setState({ loading: false, error: null })
    } catch (error) {
      setStatus(null)
      setItems([])
      setNextItem(null)
      setSelectedId(null)
      setState({ loading: false, error })
    }
  }

  useEffect(() => {
    refreshQueue()
  }, [])

  useEffect(() => {
    setSelectedReceiptPath('')
    setReceiptState({ loading: false, content: '', error: null })
    setArtifactState({ path: '', loading: false, artifact: null, error: null })
    setRunState({ running: false, result: null, error: null })
  }, [selectedId])

  const updateCreateField = (field, value) => {
    setCreateForm(current => ({ ...current, [field]: value }))
    if (createState.message || createState.error) {
      setCreateState({ submitting: false, message: '', error: null })
    }
  }

  const submitCreate = async event => {
    event.preventDefault()
    const title = createForm.title.trim()
    if (!title) {
      setCreateState({ submitting: false, message: '', error: 'Title is required.' })
      return
    }

    setCreateState({ submitting: true, message: '', error: null })
    try {
      const response = await createQueueItem({
        title,
        owner: createForm.owner || 'unassigned',
        priority: createForm.priority || 'normal',
        tags: createForm.tags,
        context: createForm.context,
      })
      if (response?.success === false || !response?.item?.id) {
        throw new Error(response?.reason || response?.message || 'Queue item was not created')
      }
      setCreateForm(emptyCreateForm)
      await refreshQueue(response.item.id)
      setCreateState({ submitting: false, message: `Created ${response.item.id}.`, error: null })
    } catch (error) {
      setCreateState({
        submitting: false,
        message: '',
        error: error?.response?.data?.detail || error?.message || 'Queue item create failed',
      })
    }
  }

  const copyPrompt = async target => {
    if (!selected?.id) return
    setPromptCopy({ target, message: '', error: null })
    try {
      const response = await getQueuePrompt(selected.id, target)
      if (response?.success === false || !response?.prompt) {
        throw new Error(response?.reason || `Unable to generate ${target} prompt`)
      }
      await copyToClipboard(response.prompt)
      setPromptCopy({ target: null, message: `${target[0].toUpperCase()}${target.slice(1)} prompt copied.`, error: null })
    } catch (error) {
      setPromptCopy({ target: null, message: '', error: error?.response?.data?.detail || error?.message || 'Prompt copy failed' })
    }
  }

  const viewReceipt = async receipt => {
    const path = receiptLabel(receipt)
    setSelectedReceiptPath(path)
    setReceiptState({ loading: true, content: '', error: null })
    try {
      const response = await getQueueReceipt(path)
      if (response?.success === false) {
        throw new Error(response?.reason || response?.message || 'Receipt unavailable')
      }
      setReceiptState({ loading: false, content: response?.content || '', error: null })
    } catch (error) {
      setReceiptState({
        loading: false,
        content: '',
        error: error?.response?.data?.detail || error?.message || 'Receipt view failed',
      })
    }
  }

  const viewArtifact = async artifact => {
    const path = artifact?.path || ''
    setArtifactState({ path, loading: true, artifact: null, error: null })
    try {
      const response = await fetch(`/api/queue/artifact?path=${encodeURIComponent(path)}`)
      const data = await response.json().catch(() => ({}))
      if (!response.ok || data?.success === false) {
        throw new Error(data?.detail || data?.reason || data?.message || 'Artifact unavailable')
      }
      setArtifactState({ path: data.path || path, loading: false, artifact: data, error: null })
    } catch (error) {
      setArtifactState({
        path,
        loading: false,
        artifact: null,
        error: error?.message || 'Artifact view failed',
      })
    }
  }

  const copyPath = async path => {
    if (!path) return
    await copyToClipboard(path)
  }

  const runAssignedWorker = async () => {
    if (!selected?.id || runState.running || selected.status === 'agent_working') return
    setRunState({ running: true, result: null, error: null })
    try {
      const response = await fetch(`/api/queue/items/${encodeURIComponent(selected.id)}/run`, { method: 'POST' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || data?.ok === false) {
        throw new Error(data?.detail || data?.reason || data?.message || 'Queue item run failed')
      }
      setRunState({ running: false, result: data, error: null })
      await refreshQueue(selected.id)
    } catch (error) {
      setRunState({
        running: false,
        result: null,
        error: error?.message || 'Queue item run failed',
      })
    }
  }

  const reason = state.error?.response?.data?.detail || state.error?.message
  const counts = status?.counts || {}
  const activeCount = status?.activeCount ?? items.filter(item => !['done', 'cancelled'].includes(item.status)).length
  const needsLiam = status?.needsLiam ?? ((counts.needs_input || 0) + (counts.human_review || 0) + (counts.blocked || 0))

  return (
    <div className="max-w-7xl space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-champagne">Queue</p>
          <h1 className="mt-1 text-2xl font-semibold text-ivory">Agentic OS Work Queue</h1>
          <p className="mt-1 text-sm text-taupe">Local queue state from queue/work_items.jsonl. Creates stay local and do not launch agents.</p>
        </div>
        <button
          type="button"
          onClick={() => refreshQueue()}
          disabled={state.loading}
          className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCw size={13} className={state.loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {state.error && (
        <div className="rounded-lg border border-clay/40 bg-clay/10 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-stone">
            <AlertCircle size={15} className="text-clay" />
            Queue load failed
          </div>
          <div className="mt-2 text-xs font-mono text-taupe">{compactReason(reason)}</div>
        </div>
      )}

      <section className="rounded-lg border border-softgraph bg-graphite p-5">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Status counts</h2>
            <div className="mt-1 font-mono text-xs text-taupe">
              Active {activeCount} / Needs Liam {needsLiam} / Total {items.length}
            </div>
          </div>
          {status?.nextAction && <div className="max-w-xl text-sm text-stone">{status.nextAction}</div>}
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {QUEUE_STATUSES.map(queueStatus => (
            <CountTile key={queueStatus} label={queueStatus} value={counts[queueStatus]} />
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(22rem,0.9fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <form onSubmit={submitCreate} className="rounded-lg border border-softgraph bg-graphite p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Plus size={14} className="text-taupe" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Create item</h2>
              </div>
              <button
                type="submit"
                disabled={createState.submitting}
                className="inline-flex items-center gap-2 rounded bg-champagne px-3 py-2 text-xs font-mono font-semibold text-ink transition-colors hover:bg-stone disabled:cursor-not-allowed disabled:opacity-60"
              >
                {createState.submitting ? 'Creating...' : 'Create'}
              </button>
            </div>

            <div className="space-y-3">
              <FieldLabel label="Title required">
                <input
                  className={fieldBase}
                  value={createForm.title}
                  onChange={event => updateCreateField('title', event.target.value)}
                  placeholder="Add a local queue item"
                  required
                />
              </FieldLabel>

              <div className="grid gap-3 sm:grid-cols-2">
                <FieldLabel label="Owner">
                  <select className={fieldBase} value={createForm.owner} onChange={event => updateCreateField('owner', event.target.value)}>
                    {QUEUE_OWNERS.map(owner => (
                      <option key={owner} value={owner}>{owner}</option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Priority">
                  <select className={fieldBase} value={createForm.priority} onChange={event => updateCreateField('priority', event.target.value)}>
                    {QUEUE_PRIORITIES.map(priority => (
                      <option key={priority} value={priority}>{priority}</option>
                    ))}
                  </select>
                </FieldLabel>
              </div>

              <FieldLabel label="Tags">
                <input
                  className={fieldBase}
                  value={createForm.tags}
                  onChange={event => updateCreateField('tags', event.target.value)}
                  placeholder="dashboard, queue"
                />
              </FieldLabel>

              <FieldLabel label="Context">
                <textarea
                  className={`${fieldBase} min-h-[5rem] resize-y`}
                  value={createForm.context}
                  onChange={event => updateCreateField('context', event.target.value)}
                  placeholder="Local details for the queued work"
                />
              </FieldLabel>
            </div>

            {(createState.message || createState.error) && (
              <div
                className={`mt-4 rounded border px-3 py-2 text-xs font-mono ${
                  createState.error ? 'border-clay/40 bg-clay/10 text-clay' : 'border-champagne/30 bg-champagne/10 text-champagne'
                }`}
              >
                {createState.error || createState.message}
              </div>
            )}
          </form>

          <div className="rounded-lg border border-softgraph bg-graphite p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ListChecks size={14} className="text-taupe" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Work items</h2>
              </div>
              <div className="font-mono text-xs text-taupe">{items.length} local</div>
            </div>

            {state.loading ? (
              <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">Loading queue.</div>
            ) : items.length > 0 ? (
              <div className="max-h-[42rem] space-y-2 overflow-y-auto pr-1">
                {items.map(item => (
                  <button
                    type="button"
                    key={item.id}
                    onClick={() => setSelectedId(item.id)}
                    className={`w-full rounded border px-3 py-3 text-left transition-colors ${
                      selectedId === item.id ? 'border-champagne bg-softgraph' : 'border-softgraph bg-ink hover:border-taupe'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-mono text-[11px] text-champagne">{item.id || 'No ID'}</div>
                        <div className="mt-1 truncate text-sm font-semibold text-ivory">{item.title || 'Untitled queue item'}</div>
                      </div>
                      {nextItem?.id === item.id && <CheckCircle2 size={14} className="mt-1 flex-shrink-0 text-champagne" />}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 font-mono text-[11px] text-taupe">
                      <span>{formatStatus(item.status)}</span>
                      <span>{item.owner || 'unassigned'}</span>
                      <span>Priority {item.priority ?? 0}</span>
                      {item.source && <span>{item.source}</span>}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center">
                <div className="text-sm font-semibold text-stone">No local queue items found.</div>
                <div className="mt-2 text-xs font-mono text-taupe">Expected path: queue/work_items.jsonl</div>
              </div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-softgraph bg-graphite p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Selected item</h2>
              <div className="mt-2 font-mono text-xs text-champagne">{selected?.id || 'No item selected'}</div>
            </div>
            {selected && (
              <div className="flex flex-wrap gap-2 sm:justify-end">
                <PromptButton target="codex" busy={promptCopy.target === 'codex'} onCopy={copyPrompt} />
                <PromptButton target="claude" busy={promptCopy.target === 'claude'} onCopy={copyPrompt} />
                <button
                  type="button"
                  onClick={runAssignedWorker}
                  disabled={runState.running || isWorkerRunning}
                  className="inline-flex items-center gap-2 rounded bg-champagne px-3 py-2 text-xs font-mono font-semibold text-ink transition-colors hover:bg-stone disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RefreshCw size={13} className={runState.running ? 'animate-spin' : ''} />
                  {runState.running ? 'Running assigned worker...' : runButtonLabel}
                </button>
              </div>
            )}
          </div>

          {selected ? (
            <div className="space-y-5">
              {(promptCopy.message || promptCopy.error) && (
                <div
                  className={`rounded border px-3 py-2 text-xs font-mono ${
                    promptCopy.error ? 'border-clay/40 bg-clay/10 text-clay' : 'border-champagne/30 bg-champagne/10 text-champagne'
                  }`}
                >
                  {promptCopy.error || promptCopy.message}
                </div>
              )}

              {(runState.running || runState.error || runState.result || showPersistedRunState) && (
                <div className="rounded border border-softgraph bg-ink">
                  <div className="border-b border-softgraph px-3 py-2 text-xs font-semibold uppercase tracking-wider text-taupe">Assigned worker run</div>
                  {runState.running ? (
                    <div className="px-3 py-5 text-xs font-mono text-taupe">Running selected item through {selected.owner || 'unassigned'}.</div>
                  ) : runState.error ? (
                    <div className="px-3 py-5 text-xs font-mono text-clay">{compactReason(runState.error)}</div>
                  ) : showPersistedRunState ? (
                    <div className="space-y-3 px-3 py-3 text-xs font-mono text-stone">
                      <div className="flex flex-wrap gap-2 text-taupe">
                        <span>{isWorkerRunning ? 'IN PROGRESS' : 'LATEST RECEIPT'}</span>
                        <span>Worker {selected.owner || 'unassigned'}</span>
                        <span>Status {formatStatus(latestReceipt?.status || selected.status)}</span>
                        {latestReceipt?.created_at && <span>{latestReceipt.created_at}</span>}
                      </div>
                      {isWorkerRunning ? (
                        <div className="text-taupe">Worker running / refresh for status.</div>
                      ) : hasReceipt ? (
                        <>
                          <div className="break-all text-champagne">Receipt: {receiptLabel(latestReceipt)}</div>
                          <div>
                            <div className="mb-1 text-[11px] uppercase tracking-wider text-taupe">Receipt summary</div>
                            <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words leading-5">{compactOutput(latestReceipt?.summary)}</pre>
                          </div>
                        </>
                      ) : (
                        <div className="text-taupe">Status is {formatStatus(selected.status)}. No receipt is attached yet.</div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3 px-3 py-3 text-xs font-mono text-stone">
                      <div className="flex flex-wrap gap-2 text-taupe">
                        <span>{runState.result?.success ? 'PASS' : 'NEEDS ATTENTION'}</span>
                        <span>Worker {runState.result?.assigned_worker || selected.owner || 'unassigned'}</span>
                        <span>Attempts {runState.result?.attempts_used ?? 'unknown'}</span>
                        <span>Status {formatStatus(runState.result?.status)}</span>
                      </div>
                      {runState.result?.receipt_path && (
                        <div className="break-all text-champagne">Receipt: {runState.result.receipt_path}</div>
                      )}
                      <div>
                        <div className="mb-1 text-[11px] uppercase tracking-wider text-taupe">Hermes review</div>
                        <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words leading-5">{compactOutput(runState.result?.hermes_review?.output || runState.result?.hermes_review?.decision)}</pre>
                      </div>
                      <div>
                        <div className="mb-1 text-[11px] uppercase tracking-wider text-taupe">Worker result</div>
                        <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words leading-5">{compactOutput(runState.result?.worker_result?.output)}</pre>
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div>
                <div className="text-xl font-semibold text-ivory">{selected.title || 'Untitled queue item'}</div>
                <div className="mt-2 flex flex-wrap gap-2 font-mono text-xs text-taupe">
                  <span>{formatStatus(selected.status)}</span>
                  <span>{selected.owner || 'unassigned'}</span>
                  <span>Priority {selected.priority ?? 0}</span>
                  {selected.source && <span>{selected.source}</span>}
                </div>
                {hasProducedArtifact && (
                  <div className="mt-3 rounded border border-champagne/30 bg-champagne/10 px-3 py-2 text-xs font-mono text-champagne">
                    human review: produced artifact available below
                  </div>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <DetailRow label="ID" value={selected.id} />
                <DetailRow label="Status" value={formatStatus(selected.status)} />
                <DetailRow label="Owner" value={selected.owner || 'unassigned'} />
                <DetailRow label="Priority" value={String(selected.priority ?? 0)} />
                <DetailRow label="Source" value={selected.source} />
                <DetailRow label="Updated at" value={selected.updated_at} />
                <DetailRow label="Created at" value={selected.created_at} />
                <DetailRow label="Requested by" value={selected.requested_by} />
                <DetailRow label="Next action" value={selected.next_action} />
                <DetailRow label="Tags" value={renderList(selected.tags)} />
                <DetailRow label="Sources" value={renderList(selected.sources)} />
                <DetailRow label="Source refs" value={renderList(selected.source_refs)} />
                <DetailRow label="Context" value={selected.context} />
                <DetailRow label="Definition of done" value={selected.definition_of_done} />
                <DetailRow label="Allowed actions" value={renderList(selected.allowed_actions)} />
                <DetailRow label="Stop conditions" value={renderList(selected.stop_conditions)} />
              </div>

              <div className="rounded border border-softgraph bg-ink">
                <div className="flex flex-col gap-2 border-b border-softgraph px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Run / artifacts</div>
                  {hasReceipt && (
                    <div className="break-all text-xs font-mono text-champagne">Latest receipt: {receiptLabel(latestReceipt)}</div>
                  )}
                </div>
                <div className="space-y-3 px-3 py-3">
                  <div>
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-taupe">Latest receipt content</div>
                    {hasReceipt ? (
                      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded border border-softgraph bg-graphite px-3 py-3 text-xs leading-5 text-stone">
                        {latestReceipt?.content || latestReceipt?.summary || 'Receipt content unavailable.'}
                      </pre>
                    ) : (
                      <div className="text-sm text-stone">No receipt is attached yet.</div>
                    )}
                  </div>
                  <div>
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-taupe">Token usage</div>
                    <pre className="whitespace-pre-wrap break-words rounded border border-softgraph bg-graphite px-3 py-2 text-xs font-mono leading-5 text-stone">
                      {tokenUsageText(latestReceipt?.token_usage_lines)}
                    </pre>
                  </div>
                  <div>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-taupe">Artifact / result files</div>
                    {runArtifacts.length ? (
                      <div className="space-y-2">
                        {runArtifacts.map((artifact, index) => (
                          <div key={`${artifact.path}-${index}`} className="rounded border border-softgraph bg-graphite px-3 py-2 text-xs font-mono text-stone">
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <div className="break-all text-champagne">{artifact.path}</div>
                                <div className="mt-1 flex flex-wrap gap-2 text-taupe">
                                  <span>{artifact.available ? 'readable' : 'unavailable'}</span>
                                  {artifact.size_bytes !== undefined && <span>{artifact.size_bytes} bytes</span>}
                                  {artifact.modified && <span>{artifact.modified}</span>}
                                  {!artifact.available && artifact.reason && <span>{artifact.reason}</span>}
                                </div>
                              </div>
                              <div className="flex flex-shrink-0 flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() => copyPath(artifact.path)}
                                  className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                                >
                                  <Clipboard size={12} />
                                  Copy path
                                </button>
                                <button
                                  type="button"
                                  onClick={() => viewArtifact(artifact)}
                                  disabled={!artifact.available}
                                  className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  <FileText size={12} />
                                  View
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-stone">No artifact paths found in the current receipt or work item.</div>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Receipt history</div>
                {selected.receipts?.length ? (
                  <div className="mt-2 space-y-2">
                    {selected.receipts.map((receipt, index) => (
                      <div key={`${receiptLabel(receipt)}-${index}`} className="rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="break-all">{receiptLabel(receipt)}</div>
                          <div className="flex flex-shrink-0 flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => copyPath(receiptLabel(receipt))}
                              className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                            >
                              <Clipboard size={12} />
                              Copy path
                            </button>
                            <button
                              type="button"
                              onClick={() => viewReceipt(receipt)}
                              className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                            >
                              <FileText size={12} />
                              View
                            </button>
                          </div>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-2 text-taupe">
                          {receipt.status && <span>{formatStatus(receipt.status)}</span>}
                          {receipt.created_at && <span>{receipt.created_at}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-1 text-sm text-stone">None</div>
                )}
              </div>

              {selectedReceiptPath && (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Receipt viewer</div>
                  <div className="mt-2 rounded border border-softgraph bg-ink">
                    <div className="border-b border-softgraph px-3 py-2 text-xs font-mono text-champagne break-all">{selectedReceiptPath}</div>
                    {receiptState.loading ? (
                      <div className="px-3 py-5 text-xs font-mono text-taupe">Loading receipt.</div>
                    ) : receiptState.error ? (
                      <div className="px-3 py-5 text-xs font-mono text-clay">{compactReason(receiptState.error)}</div>
                    ) : (
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-5 text-stone">{receiptState.content || 'Receipt is empty.'}</pre>
                    )}
                  </div>
                </div>
              )}

              {artifactState.path && (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Artifact viewer</div>
                  <div className="mt-2 rounded border border-softgraph bg-ink">
                    <div className="border-b border-softgraph px-3 py-2 text-xs font-mono text-champagne break-all">{artifactState.path}</div>
                    {artifactState.loading ? (
                      <div className="px-3 py-5 text-xs font-mono text-taupe">Loading artifact.</div>
                    ) : artifactState.error ? (
                      <div className="px-3 py-5 text-xs font-mono text-clay">{compactReason(artifactState.error)}</div>
                    ) : (
                      <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-5 text-stone">{artifactState.artifact?.content || 'Artifact is empty.'}</pre>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center text-xs font-mono text-taupe">
              {items.length ? 'Select an item to inspect details.' : 'Queue details will appear when local items exist.'}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
