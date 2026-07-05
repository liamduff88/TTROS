import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Clipboard, ListChecks, Plus, RefreshCw } from 'lucide-react'
import { createQueueItem, getQueueItem, getQueueItems, getQueueNext, getQueuePrompt, getQueueStatus } from '../api'

const OWNERS = ['unassigned', 'hermes', 'codex', 'claude', 'revenue', 'marketing', 'delivery', 'operations']
const PRIORITIES = ['low', 'normal', 'high', 'urgent']
const DEFAULT_ALLOWED = 'local_read\nlocal_edit\nlocal_test'
const DEFAULT_STOPS = 'external_send\nsecrets_exposure\ndestructive_action_outside_scope'

const emptyForm = {
  title: '',
  owner: 'unassigned',
  priority: 'normal',
  tags: '',
  context: '',
  sources: '',
  definition_of_done: '',
  allowed_actions: DEFAULT_ALLOWED,
  stop_conditions: DEFAULT_STOPS,
}

const formatStatus = value => String(value || '').replace(/_/g, ' ')

const compactReason = value => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return 'Local queue endpoint did not return a reason.'
  return text.length > 180 ? `${text.slice(0, 177).trim()}...` : text
}

const Field = ({ label, children }) => (
  <label className="block">
    <span className="text-[11px] font-semibold uppercase tracking-wider text-taupe">{label}</span>
    <div className="mt-1">{children}</div>
  </label>
)

const TextInput = props => (
  <input
    {...props}
    className="w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-ivory outline-none transition-colors placeholder:text-taupe/70 focus:border-champagne"
  />
)

const TextArea = props => (
  <textarea
    {...props}
    className="min-h-[5rem] w-full resize-y rounded border border-softgraph bg-ink px-3 py-2 text-sm text-ivory outline-none transition-colors placeholder:text-taupe/70 focus:border-champagne"
  />
)

const Select = props => (
  <select
    {...props}
    className="w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-ivory outline-none transition-colors focus:border-champagne"
  />
)

const DetailRow = ({ label, value }) => (
  <div>
    <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">{label}</div>
    <div className="mt-1 whitespace-pre-wrap text-sm text-stone">{value || 'None'}</div>
  </div>
)

const renderList = value => {
  const items = Array.isArray(value) ? value : []
  return items.length ? items.join('\n') : ''
}

const promptActionForOwner = owner => {
  const normalized = String(owner || '').toLowerCase()
  if (normalized === 'hermes') return { target: 'hermes', label: 'Copy Hermes prompt' }
  if (['revenue', 'marketing', 'delivery', 'operations'].includes(normalized)) {
    return { target: normalized, label: 'Copy Department prompt' }
  }
  return null
}

export default function Queue() {
  const [status, setStatus] = useState(null)
  const [items, setItems] = useState([])
  const [nextItem, setNextItem] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [state, setState] = useState({ loading: true, creating: false, error: null, copied: '' })

  const selectedFromList = useMemo(
    () => items.find(item => item.id === selectedId) || null,
    [items, selectedId],
  )

  const refreshQueue = async (preferredId = selectedId) => {
    setState(current => ({ ...current, loading: true, error: null, copied: '' }))
    try {
      const [statusData, itemsData, nextData] = await Promise.all([getQueueStatus(), getQueueItems(), getQueueNext()])
      if (statusData?.success === false || itemsData?.success === false || nextData?.success === false) {
        throw new Error(statusData?.reason || itemsData?.reason || nextData?.reason || 'Queue unavailable')
      }
      const list = itemsData?.items || []
      const next = nextData?.item || null
      const id = preferredId || next?.id || list[0]?.id || null
      setStatus(statusData)
      setItems(list)
      setNextItem(next)
      setSelectedId(id)
      setState(current => ({ ...current, loading: false, error: null }))
      if (id) {
        const detail = await getQueueItem(id)
        setSelected(detail?.item || null)
      } else {
        setSelected(null)
      }
    } catch (error) {
      setState(current => ({ ...current, loading: false, error, copied: '' }))
      setSelected(null)
    }
  }

  useEffect(() => {
    refreshQueue()
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setSelected(null)
      return
    }
    getQueueItem(selectedId)
      .then(data => setSelected(data?.item || null))
      .catch(error => setState(current => ({ ...current, error })))
  }, [selectedId])

  const updateForm = event => {
    const { name, value } = event.target
    setForm(current => ({ ...current, [name]: value }))
  }

  const submitForm = async event => {
    event.preventDefault()
    setState(current => ({ ...current, creating: true, error: null, copied: '' }))
    try {
      const created = await createQueueItem(form)
      const id = created?.item?.id
      setForm(emptyForm)
      await refreshQueue(id)
    } catch (error) {
      setState(current => ({ ...current, creating: false, loading: false, error, copied: '' }))
      return
    }
    setState(current => ({ ...current, creating: false }))
  }

  const copyPrompt = async target => {
    if (!selected?.id) return
    setState(current => ({ ...current, error: null, copied: '' }))
    try {
      const result = await getQueuePrompt(selected.id, target)
      if (result?.success === false) throw new Error(result.reason || 'Prompt unavailable')
      await navigator.clipboard.writeText(result.prompt || '')
      setState(current => ({ ...current, copied: 'Prompt copied.' }))
    } catch (error) {
      setState(current => ({ ...current, error, copied: '' }))
    }
  }

  const reason = state.error?.response?.data?.detail || state.error?.message
  const counts = status?.counts || {}
  const detail = selected || selectedFromList
  const ownerPromptAction = promptActionForOwner(detail?.owner)

  return (
    <div className="max-w-7xl space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-champagne">Queue</p>
          <h1 className="mt-1 text-2xl font-semibold text-ivory">Agentic OS Work Queue</h1>
          <p className="mt-1 text-sm text-taupe">Local queue creation, detail review, and manual workbench prompt copy.</p>
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
            Queue unavailable
          </div>
          <div className="mt-2 text-xs font-mono text-taupe">{compactReason(reason)}</div>
        </div>
      )}

      <section className="rounded-lg border border-softgraph bg-graphite p-5">
        <div className="mb-4 flex items-center gap-2">
          <Plus size={14} className="text-champagne" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Create queue item</h2>
        </div>
        <form onSubmit={submitForm} className="grid gap-4 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <Field label="Title">
              <TextInput name="title" value={form.title} onChange={updateForm} required placeholder="Short work item title" />
            </Field>
          </div>
          <Field label="Owner">
            <Select name="owner" value={form.owner} onChange={updateForm}>
              {OWNERS.map(owner => <option key={owner} value={owner}>{owner}</option>)}
            </Select>
          </Field>
          <Field label="Priority">
            <Select name="priority" value={form.priority} onChange={updateForm}>
              {PRIORITIES.map(priority => <option key={priority} value={priority}>{priority}</option>)}
            </Select>
          </Field>
          <div className="lg:col-span-2">
            <Field label="Tags">
              <TextInput name="tags" value={form.tags} onChange={updateForm} placeholder="dashboard, queue" />
            </Field>
          </div>
          <div className="lg:col-span-2">
            <Field label="Source references / files">
              <TextArea name="sources" value={form.sources} onChange={updateForm} placeholder="One source, path, or reference per line" />
            </Field>
          </div>
          <div className="lg:col-span-2">
            <Field label="Context">
              <TextArea name="context" value={form.context} onChange={updateForm} placeholder="Relevant local context only" />
            </Field>
          </div>
          <div className="lg:col-span-2">
            <Field label="Definition of done">
              <TextArea name="definition_of_done" value={form.definition_of_done} onChange={updateForm} />
            </Field>
          </div>
          <div className="lg:col-span-2">
            <Field label="Allowed actions">
              <TextArea name="allowed_actions" value={form.allowed_actions} onChange={updateForm} />
            </Field>
          </div>
          <div className="lg:col-span-2">
            <Field label="Stop conditions">
              <TextArea name="stop_conditions" value={form.stop_conditions} onChange={updateForm} />
            </Field>
          </div>
          <div className="lg:col-span-4">
            <button
              type="submit"
              disabled={state.creating}
              className="inline-flex items-center gap-2 rounded bg-champagne px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-stone disabled:cursor-not-allowed disabled:opacity-70"
            >
              <Plus size={14} />
              {state.creating ? 'Creating' : 'Create queue item'}
            </button>
          </div>
        </form>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(22rem,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-lg border border-softgraph bg-graphite p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ListChecks size={14} className="text-taupe" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Items</h2>
            </div>
            <div className="font-mono text-xs text-taupe">Active {status?.activeCount ?? items.length}</div>
          </div>
          <div className="mb-4 grid grid-cols-4 gap-2">
            {['inbox', 'agent_todo', 'agent_working', 'blocked'].map(key => (
              <div key={key} className="rounded border border-softgraph bg-ink px-2 py-2">
                <div className="truncate text-[10px] font-mono uppercase text-taupe">{formatStatus(key)}</div>
                <div className="mt-1 font-mono text-sm text-stone">{counts[key] ?? 0}</div>
              </div>
            ))}
          </div>
          {state.loading ? (
            <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">Loading queue.</div>
          ) : items.length > 0 ? (
            <div className="max-h-[34rem] space-y-2 overflow-y-auto pr-1">
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
                      <div className="font-mono text-[11px] text-champagne">{item.id}</div>
                      <div className="mt-1 truncate text-sm font-semibold text-ivory">{item.title || 'Untitled queue item'}</div>
                    </div>
                    {nextItem?.id === item.id && <CheckCircle2 size={14} className="mt-1 flex-shrink-0 text-champagne" />}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 font-mono text-[11px] text-taupe">
                    <span>{formatStatus(item.status)}</span>
                    <span>{item.owner || 'unassigned'}</span>
                    <span>P{item.priority ?? 0}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">No queue items yet.</div>
          )}
        </div>

        <div className="rounded-lg border border-softgraph bg-graphite p-5">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Item detail</h2>
              <div className="mt-2 font-mono text-xs text-champagne">{detail?.id || 'No item selected'}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {ownerPromptAction && (
                <button
                  type="button"
                  disabled={!detail?.id}
                  onClick={() => copyPrompt(ownerPromptAction.target)}
                  className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Clipboard size={13} />
                  {ownerPromptAction.label}
                </button>
              )}
              <button
                type="button"
                disabled={!detail?.id}
                onClick={() => copyPrompt('codex')}
                className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Clipboard size={13} />
                Copy Codex prompt
              </button>
              <button
                type="button"
                disabled={!detail?.id}
                onClick={() => copyPrompt('claude')}
                className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Clipboard size={13} />
                Copy Claude prompt
              </button>
            </div>
          </div>

          {state.copied && <div className="mb-4 rounded border border-champagne/30 bg-champagne/10 px-3 py-2 text-xs font-mono text-champagne">{state.copied}</div>}

          {detail ? (
            <div className="space-y-5">
              <div>
                <div className="text-xl font-semibold text-ivory">{detail.title || 'Untitled queue item'}</div>
                <div className="mt-2 flex flex-wrap gap-2 font-mono text-xs text-taupe">
                  <span>{formatStatus(detail.status)}</span>
                  <span>{detail.owner || 'unassigned'}</span>
                  <span>Priority {detail.priority ?? 0}</span>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <DetailRow label="Tags" value={renderList(detail.tags)} />
                <DetailRow label="Sources" value={renderList(detail.sources)} />
                <DetailRow label="Context" value={detail.context} />
                <DetailRow label="Definition of done" value={detail.definition_of_done} />
                <DetailRow label="Allowed actions" value={renderList(detail.allowed_actions)} />
                <DetailRow label="Stop conditions" value={renderList(detail.stop_conditions)} />
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Receipts</div>
                {detail.receipts?.length ? (
                  <div className="mt-2 space-y-2">
                    {detail.receipts.map((receipt, index) => (
                      <div key={`${receipt.path || index}`} className="rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone">
                        {receipt.path || 'Receipt'} {receipt.status ? `(${receipt.status})` : ''}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-1 text-sm text-stone">None</div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center text-xs font-mono text-taupe">Select an item to inspect details.</div>
          )}
        </div>
      </section>
    </div>
  )
}
