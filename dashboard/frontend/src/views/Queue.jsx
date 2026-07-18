import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, Clipboard, FileText, Focus, FolderOpen, ListChecks, Plus, RefreshCw } from 'lucide-react'
import { createQueueItem, externalActionDryRun, getQueueArtifact, getQueueItemsForScope, getQueuePrompt, getQueueReceipt, getQueueStatus, openQueueArtifactFolder } from '../api'
import { laneColor, laneName, workbenchColor } from '../shellState'
import { loadQueueScope, persistQueueScope, QUEUE_SCOPES, resolveQueueSelection } from '../queueState'
import { isReviewCardItem } from '../reviewCardState'
import { HumanReviewCard } from '../components/HumanReviewCard'

const QUEUE_STATUSES = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled']
const QUEUE_OWNERS = ['unassigned', 'hermes', 'codex', 'claude', 'revenue', 'marketing', 'delivery', 'operations']
const QUEUE_PRIORITIES = ['low', 'normal', 'high', 'urgent']
const QUEUE_SCOPE_LABELS = { active: 'Active', history: 'History', all: 'All' }

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

const artifactCategory = artifact => {
  if (artifact?.category) return artifact.category
  if (artifact?.path?.startsWith('queue/receipts/')) return 'Receipt'
  if (artifact?.extension) return `Artifact ${artifact.extension}`
  return 'Artifact'
}

const fileTypeText = preview => {
  if (!preview?.path) return 'No file selected'
  const extension = preview.extension || ''
  return [preview.category, extension].filter(Boolean).join(' / ') || 'Text file'
}

const scrollFilePreviewIntoView = () => {
  window.requestAnimationFrame(() => {
    document.getElementById('queue-file-preview')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })
}

const REVIEW_OR_COMPLETE_STATUSES = new Set(['human_review', 'done', 'blocked', 'needs_input'])

const itemLane = item => item?.lane || item?.owner || 'unassigned'

const NEEDS_ME_STATUSES = new Set(['human_review', 'needs_input', 'blocked'])

const matchesFilters = (item, filters) =>
  (!filters.needsMe || NEEDS_ME_STATUSES.has(item.status) || (Array.isArray(item.needs_me) && item.needs_me.length > 0)) &&
  (!filters.status || item.status === filters.status) &&
  (!filters.workbench || item.owner === filters.workbench) &&
  (!filters.lane || itemLane(item) === filters.lane) &&
  (!filters.source || String(item.source || '').toLowerCase() === String(filters.source).toLowerCase())

const selectedIdFromParams = params => params?.selectedId || params?.itemId || null

const filtersFromParams = params => {
  const { selectedId, itemId, ...filters } = params || {}
  return filters
}

const emptyCreateForm = {
  title: '',
  owner: 'unassigned',
  priority: 'normal',
  tags: '',
  source: 'dashboard',
  context: '',
  sources: '',
  source_refs: '',
  allowed_actions: 'local_read, local_edit, local_test',
  stop_conditions: 'external_send, secrets_exposure, destructive_action_outside_scope',
  definition_of_done: '',
  parent_id: '',
  step_index: '',
  depends_on: '',
  on_complete: '',
  workbench: '',
}

const emptyDryRunForm = { recipient: '', action: '', payload: '', confirmation: '' }
const emptyDryRunState = { submitting: false, message: '', error: null, receiptPath: '' }

// Locked safety distinction: internal-live ≠ third-party-live.
const manualPlatformUrl = action => /linkedin|post|publish/i.test(action || '')
  ? 'https://www.linkedin.com/'
  : /email|mail|proposal/i.test(action || '')
    ? 'https://mail.google.com/'
    : ''

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

export const toggleQueueStatusFilter = (filters, status) => {
  if (filters.status !== status) return { ...filters, status }
  const { status: _status, ...remainingFilters } = filters
  return remainingFilters
}

export const CountTile = ({ status, value, active, onToggle }) => (
  <button
    type="button"
    onClick={() => onToggle(status)}
    aria-pressed={active}
    className={`cursor-pointer rounded border px-3 py-3 text-left transition-colors ${
      active
        ? 'border-champagne/40 bg-champagne/10'
        : 'border-softgraph bg-ink hover:border-champagne/40 hover:bg-champagne/10'
    }`}
  >
    <div className={`truncate text-[10px] font-mono uppercase ${active ? 'text-champagne' : 'text-taupe'}`}>{formatStatus(status)}</div>
    <div className={`mt-1 font-mono text-lg ${active ? 'text-champagne' : 'text-stone'}`}>{value ?? 0}</div>
  </button>
)

export const QueueFilterChip = ({ filters, onClear }) => {
  const label = [filters.status && formatStatus(filters.status), filters.workbench, filters.lane, filters.source].filter(Boolean).join(' / ')
  if (!label) return null
  return (
    <button
      type="button"
      onClick={onClear}
      className="inline-flex items-center gap-1.5 rounded border border-champagne/40 bg-champagne/10 px-2 py-1 text-[11px] font-mono text-champagne transition-colors hover:bg-champagne/20"
    >
      Filtered: {label} ×
    </button>
  )
}

const fieldBase =
  'mt-1 w-full rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none transition-colors placeholder:text-taupe focus:border-champagne'

const FieldLabel = ({ label, children }) => (
  <label className="block">
    <span className="text-[11px] font-semibold uppercase tracking-wider text-taupe">{label}</span>
    {children}
  </label>
)

export default function Queue({ initialFilters = {}, onViewParamsChange, refresh }) {
  const initialSelectedId = selectedIdFromParams(initialFilters)
  const [status, setStatus] = useState(null)
  const [items, setItems] = useState([])
  const [scope, setScope] = useState(() => loadQueueScope())
  const [nextItem, setNextItem] = useState(null)
  const [selectedId, setSelectedId] = useState(initialSelectedId)
  const [filters, setFilters] = useState(filtersFromParams(initialFilters))
  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [createState, setCreateState] = useState({ submitting: false, message: '', error: null })
  const [promptCopy, setPromptCopy] = useState({ target: null, message: '', error: null })
  const [runState, setRunState] = useState({ running: false, result: null, error: null })
  const [dryRunForm, setDryRunForm] = useState(emptyDryRunForm)
  const [dryRunState, setDryRunState] = useState(emptyDryRunState)
  const [finalStepSelection, setFinalStepSelection] = useState({ targetId: '', message: '' })
  const [focusMode, setFocusMode] = useState(false)
  const [listCollapsed, setListCollapsed] = useState(Boolean(initialSelectedId))
  const selectedDetailRef = useRef(null)
  const selectedIdRef = useRef(initialSelectedId)
  const selectionRevisionRef = useRef(0)
  const refreshRequestRef = useRef(0)
  const [filePreview, setFilePreview] = useState({
    path: '',
    category: '',
    extension: '',
    loading: false,
    content: '',
    error: null,
  })
  const [state, setState] = useState({ loading: true, error: null })

  const filteredItems = useMemo(
    () => items.filter(item => matchesFilters(item, filters)),
    [items, filters],
  )
  const selected = useMemo(
    () => items.find(item => item.id === selectedId) || null,
    [items, selectedId],
  )
  const selectedStatus = selected?.status || ''
  const finalResult = selected?.final_result || null
  const pipeline = selected?.pipeline || null
  const latestReceipt = selected?.latest_receipt || (selected?.receipts?.length ? selected.receipts[selected.receipts.length - 1] : null)
  const hasReceipt = Boolean(receiptLabel(latestReceipt) && latestReceipt && receiptLabel(latestReceipt) !== 'Receipt path unavailable')
  const runArtifacts = Array.isArray(selected?.run_artifacts) ? selected.run_artifacts : []
  const hasProducedArtifact = selectedStatus === 'human_review' && runArtifacts.some(artifact => artifact.available && artifact.path !== receiptLabel(latestReceipt))
  const isReviewOrComplete = REVIEW_OR_COMPLETE_STATUSES.has(selectedStatus)
  const isWorkerRunning = selectedStatus === 'agent_working'
  const isStuckWorker = Boolean(selected?.stuck_recovery?.stuck)
  const showPersistedRunState = Boolean(selected && (hasReceipt || isReviewOrComplete || isWorkerRunning) && !runState.result && !runState.error && !runState.running)
  const runButtonLabel = isWorkerRunning
    ? isStuckWorker ? 'Recover stuck worker' : 'Worker running / refresh for status'
    : hasReceipt || isReviewOrComplete
      ? 'Rerun assigned worker'
      : 'Run assigned worker'

  const selectQueueItem = (id, notify = true) => {
    selectedIdRef.current = id
    selectionRevisionRef.current += 1
    setSelectedId(id)
    if (id && notify) setListCollapsed(true)
    if (notify) onViewParamsChange?.({ ...filters, selectedId: id })
  }

  const refreshQueue = async (preferredId = null) => {
    const requestId = ++refreshRequestRef.current
    const selectionRevision = selectionRevisionRef.current
    setState({ loading: true, error: null })
    try {
      const [statusData, itemsData] = await Promise.all([getQueueStatus(), getQueueItemsForScope(scope)])
      if (statusData?.success === false || itemsData?.success === false) {
        throw new Error(statusData?.reason || itemsData?.reason || 'Queue unavailable')
      }

      const list = sortQueueItemsNewestFirst(itemsData?.items || [])
      const next = statusData?.nextItem || null
      if (requestId !== refreshRequestRef.current) return
      const resolvedId = resolveQueueSelection({
        items: list,
        currentId: selectedIdRef.current,
        preferredId,
        nextId: next?.id,
        selectionChanged: selectionRevisionRef.current !== selectionRevision,
      })
      setStatus(statusData)
      setItems(list)
      setNextItem(next)
      selectedIdRef.current = resolvedId
      setSelectedId(resolvedId)
      onViewParamsChange?.({ ...filters, selectedId: resolvedId })
      setState({ loading: false, error: null })
    } catch (error) {
      if (requestId !== refreshRequestRef.current) return
      setState({ loading: false, error })
    }
  }

  useEffect(() => {
    persistQueueScope(scope)
    refreshQueue()
  }, [scope])

  useEffect(() => {
    if (selectedId) setListCollapsed(true)
  }, [selectedId])

  useEffect(() => {
    const explicitSelectedId = selectedIdFromParams(initialFilters)
    setFilters(filtersFromParams(initialFilters))
    if (explicitSelectedId && explicitSelectedId !== selectedIdRef.current) selectQueueItem(explicitSelectedId, false)
  }, [JSON.stringify(initialFilters)])

  useEffect(() => {
    if (state.loading || !items.length) return
    if (filteredItems.some(item => item.id === selectedId)) return
    selectQueueItem(filteredItems[0]?.id || null)
  }, [filteredItems, state.loading])

  useEffect(() => {
    setFilePreview({ path: '', category: '', extension: '', loading: false, content: '', error: null })
    setRunState({ running: false, result: null, error: null })
    setDryRunForm(emptyDryRunForm)
    setDryRunState(emptyDryRunState)
  }, [selectedId])

  useEffect(() => {
    if (!finalStepSelection.targetId || finalStepSelection.targetId !== selected?.id) return
    window.requestAnimationFrame(() => {
      const panel = selectedDetailRef.current
      if (!panel) return
      panel.scrollTop = 0
      panel.scrollIntoView({ block: 'start', behavior: 'smooth' })
    })
  }, [selected?.id, finalStepSelection.targetId])

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
        source: createForm.source,
        context: createForm.context,
        sources: createForm.sources,
        source_refs: createForm.source_refs,
        allowed_actions: createForm.allowed_actions,
        stop_conditions: createForm.stop_conditions,
        definition_of_done: createForm.definition_of_done,
        parent_id: createForm.parent_id,
        step_index: createForm.step_index === '' ? null : Number(createForm.step_index),
        depends_on: createForm.depends_on,
        on_complete: createForm.on_complete,
        workbench: createForm.workbench,
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
    setFilePreview({ path, category: 'Receipt history', extension: '.md', loading: true, content: '', error: null })
    scrollFilePreviewIntoView()
    try {
      const response = await getQueueReceipt(path)
      if (response?.success === false) {
        throw new Error(response?.reason || response?.message || 'Receipt unavailable')
      }
      setFilePreview({
        path: response?.path || path,
        category: 'Receipt history',
        extension: '.md',
        loading: false,
        content: response?.content || '',
        error: null,
      })
    } catch (error) {
      setFilePreview({
        path,
        category: 'Receipt history',
        extension: '.md',
        loading: false,
        content: '',
        error: error?.response?.data?.detail || error?.message || 'Receipt view failed',
      })
    }
  }

  const viewArtifact = async artifact => {
    const path = artifact?.path || ''
    const category = artifactCategory(artifact)
    const extension = artifact?.extension || ''
    if (!artifact?.available) {
      setFilePreview({
        path,
        category,
        extension,
        loading: false,
        content: '',
        error: artifact?.reason || 'File is listed but is not available to preview.',
      })
      scrollFilePreviewIntoView()
      return
    }
    setFilePreview({ path, category, extension, loading: true, content: '', error: null })
    scrollFilePreviewIntoView()
    try {
      const data = await getQueueArtifact(path)
      if (data?.success === false) {
        throw new Error(data?.reason || data?.message || 'Artifact unavailable')
      }
      setFilePreview({
        path: data.path || path,
        category,
        extension: data.extension || extension,
        loading: false,
        content: data.content || '',
        error: null,
      })
    } catch (error) {
      setFilePreview({
        path,
        category,
        extension,
        loading: false,
        content: '',
        error: error?.message || 'Artifact view failed',
      })
    }
  }

  const copyPath = async path => {
    if (!path) return
    await copyToClipboard(path)
  }

  const runAssignedWorker = async () => {
    if (!selected?.id || runState.running || (selected.status === 'agent_working' && !isStuckWorker)) return
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

  const updateDryRunField = (field, value) => {
    setDryRunForm(current => ({ ...current, [field]: value }))
    if (dryRunState.message || dryRunState.error) setDryRunState(emptyDryRunState)
  }

  const submitDryRun = async event => {
    event.preventDefault()
    if (!selected?.id || dryRunState.submitting) return
    setDryRunState({ submitting: true, message: '', error: null, receiptPath: '' })
    try {
      const response = await externalActionDryRun({
        item_id: selected.id,
        recipient: dryRunForm.recipient,
        action: dryRunForm.action,
        payload: dryRunForm.payload,
        confirmation: dryRunForm.confirmation,
      })
      if (response?.success === false || response?.dry_run !== true || response?.transmitted !== false) {
        throw new Error(response?.reason || response?.message || 'Dry-run receipt failed')
      }
      await refreshQueue(selected.id)
      setDryRunState({ submitting: false, message: 'Dry-run receipt written. No external transmission occurred.', error: null, receiptPath: response.receipt_path || '' })
    } catch (error) {
      setDryRunState({ submitting: false, message: '', error: error?.response?.data?.detail || error?.message || 'Dry-run confirmation failed', receiptPath: '' })
    }
  }

  const reason = state.error?.response?.data?.detail || state.error?.message
  const counts = status?.counts || {}
  const activeCount = status?.activeCount ?? items.filter(item => !['done', 'cancelled'].includes(item.status)).length
  const totalCount = status?.totalCount ?? Object.values(counts).reduce((total, value) => total + (Number(value) || 0), 0)
  const needsLiam = status?.needsLiam ?? ((counts.needs_input || 0) + (counts.human_review || 0) + (counts.blocked || 0))
  const latestReceiptPath = receiptLabel(latestReceipt)
  const primaryOutputPath = runArtifacts.find(artifact => artifact.available && artifact.path !== latestReceiptPath)?.path || ''
  const finalArtifact = finalResult?.final_artifacts?.find(artifact => artifact.available) || (finalResult?.final_artifact_paths?.[0] ? { path: finalResult.final_artifact_paths[0], available: true, category: 'Final review package', extension: '.md' } : null)
  const finalReceipt = finalResult?.final_receipts?.find(receipt => receipt.available) || (finalResult?.final_receipt_paths?.[0] ? { path: finalResult.final_receipt_paths[0], available: true, category: 'Final receipt', extension: '.md' } : null)
  const finalArtifactName = finalArtifact?.name || finalArtifact?.path?.split('/').pop() || '03_final_review_package.md'
  const finalStepSelectionMessage = finalStepSelection.targetId && finalStepSelection.targetId === selected?.id ? finalStepSelection.message : ''

  const openFinalFolder = async () => {
    if (!finalArtifact?.path) return
    try {
      await openQueueArtifactFolder(finalArtifact.path)
    } catch (error) {
      setFilePreview({
        path: finalArtifact.path,
        category: 'Output folder',
        extension: '',
        loading: false,
        content: '',
        error: error?.response?.data?.detail || error?.message || 'Output folder open failed',
      })
      scrollFilePreviewIntoView()
    }
  }

  const viewFinalStep = () => {
    const finalItemId = finalResult?.final_item_id
    if (!finalItemId) return
    setFilters({})
    selectQueueItem(finalItemId)
    setFinalStepSelection({ targetId: finalItemId, message: 'Final step selected' })
  }

  return (
    <div className="max-w-7xl space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-champagne">Queue</p>
          <h1 className="mt-1 text-2xl font-semibold text-ivory">Agentic OS Work Queue</h1>
          <p className="mt-1 text-sm text-taupe">Local queue state from queue/work_items.jsonl. Creates stay local and do not launch agents.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => setFocusMode(value => !value)} aria-pressed={focusMode} className={`inline-flex items-center gap-2 rounded border px-3 py-2 text-xs font-mono ${focusMode ? 'border-[var(--wb-codex-queued)] bg-[var(--wb-codex-done)] text-[var(--wb-codex-dark)]' : 'border-softgraph bg-ink text-taupe'}`} data-testid="focus-mode-toggle"><Focus size={13} />{focusMode ? 'Exit focus' : 'Focus task'}</button>
          <button type="button" onClick={() => refreshQueue()} disabled={state.loading} className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone disabled:cursor-not-allowed disabled:opacity-60"><RefreshCw size={13} className={state.loading ? 'animate-spin' : ''} />Refresh</button>
        </div>
      </div>
      <div className="inline-flex w-fit rounded border border-softgraph bg-graphite p-1" role="group" aria-label="Queue scope" data-testid="queue-scope-control">
        {QUEUE_SCOPES.map(value => (
          <button
            type="button"
            key={value}
            aria-pressed={scope === value}
            onClick={() => setScope(value)}
            className={`rounded px-4 py-2 text-xs font-mono transition-colors ${scope === value ? 'bg-champagne text-ivory' : 'text-taupe hover:bg-ink hover:text-stone'}`}
          >
            {QUEUE_SCOPE_LABELS[value]}
          </button>
        ))}
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
              Active {activeCount} / Needs Me {needsLiam} / Total {totalCount}
            </div>
          </div>
          {status?.nextAction && <div className="max-w-xl text-sm text-stone">{status.nextAction}</div>}
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {QUEUE_STATUSES.map(queueStatus => (
            <CountTile
              key={queueStatus}
              status={queueStatus}
              value={counts[queueStatus]}
              active={filters.status === queueStatus}
              onToggle={statusFilter => setFilters(current => toggleQueueStatusFilter(current, statusFilter))}
            />
          ))}
        </div>
      </section>

      {focusMode && (
        <div className="flex gap-1 overflow-x-auto rounded border border-softgraph bg-graphite p-2" data-testid="focus-mini-rail">
          {filteredItems.filter(item => item.id !== selectedId).map(item => (
            <button key={item.id} onClick={() => selectQueueItem(item.id)} className="relative flex h-9 shrink-0 items-center gap-2 overflow-hidden rounded border border-softgraph bg-ink pl-3 pr-2 font-mono text-[10px] text-stone" aria-label={`Focus ${item.id}`}>
              <span className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: workbenchColor(item.invocation_source, item.status) }} />
              <span>{item.id}</span><span className="h-2 w-2 rounded-full" style={{ backgroundColor: workbenchColor(item.invocation_source, item.status) }} />
            </button>
          ))}
        </div>
      )}

      <section className={`grid gap-4 ${focusMode ? 'grid-cols-1' : listCollapsed ? 'lg:grid-cols-[10rem_minmax(0,1fr)]' : 'lg:grid-cols-[minmax(22rem,0.9fr)_minmax(0,1.1fr)]'}`} data-list-collapsed={listCollapsed ? 'true' : 'false'}>
        <div className={`space-y-4 ${focusMode ? 'hidden' : ''}`}>
          <details className={`rounded-lg border border-softgraph bg-graphite p-5 ${listCollapsed ? 'hidden' : ''}`}>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-champagne">Advanced / manual create</summary>
          <form onSubmit={submitCreate} className="mt-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Plus size={14} className="text-taupe" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Create item</h2>
              </div>
              <button
                type="submit"
                disabled={createState.submitting}
                className="inline-flex items-center gap-2 rounded bg-champagne px-3 py-2 text-xs font-mono font-semibold text-ivory transition-colors hover:bg-well disabled:cursor-not-allowed disabled:opacity-60"
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

              <FieldLabel label="Source">
                <input
                  className={fieldBase}
                  value={createForm.source}
                  onChange={event => updateCreateField('source', event.target.value)}
                  placeholder="dashboard"
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

              <FieldLabel label="Sources / files">
                <textarea
                  className={`${fieldBase} min-h-[4rem] resize-y`}
                  value={createForm.sources}
                  onChange={event => updateCreateField('sources', event.target.value)}
                  placeholder={'queue/work_items.jsonl\ndashboard/frontend/src/views/Queue.jsx'}
                />
              </FieldLabel>

              <FieldLabel label="Source refs / artifact refs">
                <textarea
                  className={`${fieldBase} min-h-[4rem] resize-y`}
                  value={createForm.source_refs}
                  onChange={event => updateCreateField('source_refs', event.target.value)}
                  placeholder={'workflows/.../output.md\nqueue/receipts/...md'}
                />
              </FieldLabel>

              <FieldLabel label="Allowed actions">
                <textarea
                  className={`${fieldBase} min-h-[4rem] resize-y`}
                  value={createForm.allowed_actions}
                  onChange={event => updateCreateField('allowed_actions', event.target.value)}
                  placeholder="local_read, local_edit, local_test"
                />
              </FieldLabel>

              <FieldLabel label="Stop conditions">
                <textarea
                  className={`${fieldBase} min-h-[4rem] resize-y`}
                  value={createForm.stop_conditions}
                  onChange={event => updateCreateField('stop_conditions', event.target.value)}
                  placeholder="external_send, secrets_exposure"
                />
              </FieldLabel>

              <FieldLabel label="Definition of done">
                <textarea
                  className={`${fieldBase} min-h-[4rem] resize-y`}
                  value={createForm.definition_of_done}
                  onChange={event => updateCreateField('definition_of_done', event.target.value)}
                  placeholder="Concrete acceptance criteria for this queue item"
                />
              </FieldLabel>

              <div className="grid gap-3 sm:grid-cols-2">
                <FieldLabel label="Parent ID">
                  <input className={fieldBase} value={createForm.parent_id} onChange={event => updateCreateField('parent_id', event.target.value)} placeholder="AOS-YYYY-NNNN" />
                </FieldLabel>
                <FieldLabel label="Step index">
                  <input type="number" className={fieldBase} value={createForm.step_index} onChange={event => updateCreateField('step_index', event.target.value)} placeholder="0" />
                </FieldLabel>
                <FieldLabel label="Depends on">
                  <input className={fieldBase} value={createForm.depends_on} onChange={event => updateCreateField('depends_on', event.target.value)} placeholder="AOS-YYYY-NNNN, AOS-YYYY-NNNN" />
                </FieldLabel>
                <FieldLabel label="On complete">
                  <input className={fieldBase} value={createForm.on_complete} onChange={event => updateCreateField('on_complete', event.target.value)} placeholder="queue_next_step" />
                </FieldLabel>
                <FieldLabel label="Workbench">
                  <input className={fieldBase} value={createForm.workbench} onChange={event => updateCreateField('workbench', event.target.value)} placeholder="codex, claude, lane" />
                </FieldLabel>
              </div>
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
          </details>

          <div className={`rounded-lg border border-softgraph bg-graphite ${listCollapsed ? 'p-2' : 'p-5'}`}>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ListChecks size={14} className="text-taupe" />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">{listCollapsed ? QUEUE_SCOPE_LABELS[scope] : `${QUEUE_SCOPE_LABELS[scope]} work items`}</h2>
              </div>
              <div className={`items-center gap-2 ${listCollapsed ? 'hidden' : 'flex'}`}>
                <QueueFilterChip filters={filters} onClear={() => setFilters({})} />
                <div className="font-mono text-xs text-taupe">{filteredItems.length} of {items.length}</div>
              </div>
            </div>

            {state.loading ? (
              <div className="rounded border border-softgraph bg-ink px-4 py-8 text-center text-xs font-mono text-taupe">Loading queue.</div>
            ) : filteredItems.length > 0 ? (
              <div className="max-h-[42rem] space-y-2 overflow-y-auto pr-1">
                {filteredItems.map(item => (
                  <button
                    type="button"
                    key={item.id}
                    onClick={() => selectQueueItem(item.id)}
                    className={`w-full rounded border text-left transition-colors ${listCollapsed ? 'px-2 py-2' : 'px-3 py-3'} ${selectedId === item.id ? 'bg-softgraph' : 'bg-ink hover:bg-well'}`}
                    style={{ borderColor: workbenchColor(item.invocation_source, item.status) }}
                    data-queue-card-id={item.id}
                    data-invocation-source={item.invocation_source || 'unattributed'}
                    aria-pressed={selectedId === item.id}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-mono text-[11px] text-champagne">{item.id || 'No ID'}</div>
                        {!listCollapsed && <div className="mt-1 truncate text-sm font-semibold text-ivory">{item.title || 'Untitled queue item'}</div>}
                      </div>
                      {nextItem?.id === item.id && <CheckCircle2 size={14} className="mt-1 flex-shrink-0 text-champagne" />}
                    </div>
                    <div className={`${listCollapsed ? 'mt-1' : 'mt-2'} flex flex-wrap items-center gap-2 font-mono text-[11px] text-taupe`}>
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ backgroundColor: laneColor(laneName(item)) }}>{laneName(item)}</span>
                      <span>{formatStatus(item.status)}</span>
                      {!listCollapsed && <><span>{item.owner || 'unassigned'}</span><span>Priority {item.priority ?? 0}</span>{item.source && <span>{item.source}</span>}</>}
                      {!listCollapsed && Array.isArray(item.needs_me) && item.needs_me.map(reason => <span key={reason} className="rounded border border-champagne/50 bg-champagne/10 px-1.5 py-0.5 text-champagne">{reason}</span>)}
                    </div>
                  </button>
                ))}
              </div>
            ) : items.length > 0 ? (
              <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center">
                <div className="text-sm font-semibold text-stone">No queue items match this filter.</div>
                <button type="button" onClick={() => setFilters({})} className="mt-2 text-xs font-mono text-champagne hover:text-stone">Clear filter</button>
              </div>
            ) : (
              <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center">
                <div className="text-sm font-semibold text-stone">No {QUEUE_SCOPE_LABELS[scope].toLowerCase()} queue items found.</div>
              </div>
            )}
          </div>
        </div>

        {selected && isReviewCardItem(selected) ? (
          <HumanReviewCard
            item={selected}
            className="self-start"
            onSaved={async () => {
              await refreshQueue(selected.id)
              await refresh?.()
            }}
          />
        ) : (
        <div id="queue-selected-detail" ref={selectedDetailRef} className="rounded-lg border bg-graphite p-5" style={{ borderColor: selected ? workbenchColor(selected.invocation_source, selected.status) : 'var(--hairline)' }} data-testid="queue-selected-detail" data-selected-item-id={selected?.id || ''} data-invocation-source={selected?.invocation_source || 'unattributed'}>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Selected item</h2>
              <div className="mt-2 flex items-center gap-2 font-mono text-xs text-champagne">
                {selected?.id || 'No item selected'}
                {selected && <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ backgroundColor: laneColor(laneName(selected)) }}>{laneName(selected)}</span>}
              </div>
            </div>
            {selected && (
              <div className="flex flex-wrap gap-2 sm:justify-end">
                {listCollapsed && !focusMode && (
                  <button type="button" onClick={() => setListCollapsed(false)} className="inline-flex items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone hover:border-champagne">
                    <ListChecks size={13} />Expand work items
                  </button>
                )}
                <PromptButton target="codex" busy={promptCopy.target === 'codex'} onCopy={copyPrompt} />
                <PromptButton target="claude" busy={promptCopy.target === 'claude'} onCopy={copyPrompt} />
                <button
                  type="button"
                  onClick={runAssignedWorker}
                  disabled={runState.running || (isWorkerRunning && !isStuckWorker)}
                  className="inline-flex items-center gap-2 rounded bg-champagne px-3 py-2 text-xs font-mono font-semibold text-ivory transition-colors hover:bg-well disabled:cursor-not-allowed disabled:opacity-60"
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

              {finalStepSelectionMessage && (
                <div className="rounded border border-champagne/30 bg-champagne/10 px-3 py-2 text-xs font-mono text-champagne">
                  {finalStepSelectionMessage}
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
                        <div className="text-taupe">
                          {isStuckWorker ? `Stuck recovery available: ${selected.stuck_recovery?.reason || 'agent_working exceeded timeout.'}` : 'Worker running / refresh for status.'}
                        </div>
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
                  {selected.honest_status && <span>{formatStatus(selected.honest_status)}</span>}
                  {selected.step_progress?.label && <span>{selected.step_progress.label}</span>}
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

              {pipeline?.nodes?.length > 0 && (
                <div className="rounded border border-softgraph bg-ink" data-testid="pipeline-visualization">
                  <div className="border-b border-softgraph px-3 py-2">
                    <div className="text-sm font-semibold text-ivory">Workflow pipeline</div>
                    <div className="mt-1 text-xs font-mono text-taupe">{pipeline.mode === 'workflow_chain' ? `Recorded chain ${pipeline.parent_id}` : 'Honest status-stage fallback; no step contract recorded'}</div>
                  </div>
                  <div className="overflow-x-auto p-3">
                    <div className="flex min-w-max items-stretch gap-2">
                      {pipeline.nodes.map((node, index) => (
                        <div key={node.id} className="flex items-center gap-2">
                          {index > 0 && <span className="text-champagne" aria-hidden="true">→</span>}
                          <article className="w-56 rounded border border-softgraph bg-graphite p-3 text-xs" data-pipeline-node={node.id}>
                            <div className="flex items-start justify-between gap-2"><span className="font-semibold text-stone">{node.name}</span><span className="rounded bg-softgraph px-1.5 py-0.5 text-[10px] text-taupe">{formatStatus(node.status)}</span></div>
                            <div className="mt-2 text-taupe">{node.timestamp || 'timestamp unavailable'}</div>
                            <div className="mt-1 text-taupe">{node.execution}</div>
                            <div className="mt-1 text-taupe">Depends on: {node.depends_on?.join(', ') || 'none recorded'}</div>
                            {node.gate && <div className="mt-2 rounded border border-champagne/50 bg-champagne/10 p-1.5 text-champagne">Gate: {formatStatus(node.gate)}</div>}
                            <div className="mt-2 flex flex-wrap gap-1">
                              {(node.receipts || []).map((receipt, receiptIndex) => <button key={`${node.id}-receipt-${receiptIndex}`} onClick={() => viewReceipt(receipt)} className="rounded border border-softgraph bg-ink px-1.5 py-1 text-[10px] text-stone">Receipt</button>)}
                              {(node.artifacts || []).map((path, artifactIndex) => <button key={`${node.id}-artifact-${artifactIndex}`} onClick={() => viewArtifact({ path, category: 'Pipeline artifact' })} className="rounded border border-softgraph bg-ink px-1.5 py-1 text-[10px] text-stone">Artifact</button>)}
                            </div>
                          </article>
                        </div>
                      ))}
                    </div>
                    {pipeline.history?.length > 0 && <div className="mt-3 rounded border border-softgraph bg-graphite p-2 text-xs text-taupe">Review/auto-resume history: {pipeline.history.map(row => `${row.event} ${row.item_id || ''} ${row.timestamp || ''}`).join(' · ')}</div>}
                  </div>
                </div>
              )}

              {finalResult?.complete && (
                <div className="rounded border border-champagne/40 bg-ink">
                  <div className="border-b border-softgraph px-3 py-2">
                    <div className="text-sm font-semibold text-ivory">Workflow complete</div>
                    <div className="mt-1 text-xs font-mono text-taupe">
                      Parent {finalResult.parent_id || 'unknown'} / Final step {finalResult.final_item_id || 'unknown'} / Status {formatStatus(finalResult.final_item_status || finalResult.chain_status)}
                    </div>
                  </div>
                  <div className="space-y-3 px-3 py-3">
                    <div className="text-xs font-mono text-champagne">Finished result: {finalArtifactName}</div>
                    <button
                      type="button"
                      aria-label="Open Final Review Package"
                      onClick={() => viewArtifact({ ...finalArtifact, category: 'Final review package', extension: finalArtifact?.extension || '.md' })}
                      disabled={!finalArtifact?.path}
                      className="inline-flex min-h-11 w-full min-w-0 items-center justify-center gap-2 whitespace-normal rounded bg-champagne px-4 py-3 text-center text-xs font-mono font-semibold leading-5 text-ivory transition-colors hover:bg-well disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <FileText size={14} className="shrink-0" />
                      <span className="min-w-0 break-words">Open Finished Result</span>
                    </button>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        aria-label="Open Final Receipt"
                        onClick={() => viewReceipt(finalReceipt)}
                        disabled={!finalReceipt?.path}
                        className="inline-flex min-h-10 min-w-[10rem] flex-1 items-center justify-center gap-2 whitespace-normal rounded border border-softgraph bg-graphite px-3 py-2 text-center text-xs font-mono font-semibold leading-5 text-stone transition-colors hover:border-champagne disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none"
                      >
                        <FileText size={13} className="shrink-0" />
                        <span className="min-w-0 break-words">Open Receipt</span>
                      </button>
                      <button
                        type="button"
                        onClick={openFinalFolder}
                        disabled={!finalArtifact?.path}
                        className="inline-flex min-h-10 min-w-[10rem] flex-1 items-center justify-center gap-2 whitespace-normal rounded border border-softgraph bg-graphite px-3 py-2 text-center text-xs font-mono font-semibold leading-5 text-stone transition-colors hover:border-champagne disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none"
                      >
                        <FolderOpen size={13} className="shrink-0" />
                        <span className="min-w-0 break-words">Open Output Folder</span>
                      </button>
                      <button
                        type="button"
                        onClick={viewFinalStep}
                        disabled={!finalResult.final_item_id}
                        className="inline-flex min-h-10 min-w-[10rem] flex-1 items-center justify-center gap-2 whitespace-normal rounded border border-softgraph bg-graphite px-3 py-2 text-center text-xs font-mono font-semibold leading-5 text-stone transition-colors hover:border-champagne disabled:cursor-not-allowed disabled:opacity-60 sm:flex-none"
                      >
                        <ListChecks size={13} className="shrink-0" />
                        <span className="min-w-0 break-words">View Final Step</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div className="grid gap-4 md:grid-cols-2">
                <DetailRow label="ID" value={selected.id} />
                <DetailRow label="Status" value={formatStatus(selected.status)} />
                <DetailRow label="Running status" value={formatStatus(selected.honest_status)} />
                <DetailRow label="Step progress" value={selected.step_progress?.label || (selected.workflow_steps?.length ? `0 of ${selected.workflow_steps.length}` : '')} />
                <DetailRow label="Owner" value={selected.owner || 'unassigned'} />
                <DetailRow label="Workbench" value={selected.workbench} />
                <DetailRow label="Priority" value={String(selected.priority ?? 0)} />
                <DetailRow label="Source" value={selected.source} />
                <DetailRow label="Updated at" value={selected.updated_at} />
                <DetailRow label="Created at" value={selected.created_at} />
                <DetailRow label="Requested by" value={selected.requested_by} />
                <DetailRow label="Next action" value={selected.next_action} />
                <DetailRow label="Parent ID" value={selected.parent_id} />
                <DetailRow label="Depends on" value={renderList(selected.depends_on)} />
                <DetailRow label="On complete" value={selected.on_complete} />
                <DetailRow label="Tags" value={renderList(selected.tags)} />
                <DetailRow label="Sources" value={renderList(selected.sources)} />
                <DetailRow label="Source refs" value={renderList(selected.source_refs)} />
                <DetailRow label="Context" value={selected.context} />
                <DetailRow label="Definition of done" value={selected.definition_of_done} />
                <DetailRow label="Allowed actions" value={renderList(selected.allowed_actions)} />
                <DetailRow label="Stop conditions" value={renderList(selected.stop_conditions)} />
              </div>

              <form onSubmit={submitDryRun} className="rounded border border-champagne/30 bg-ink" data-testid="manual-handoff">
                <div className="border-b border-softgraph px-3 py-2">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-champagne">Manual third-party handoff / dry-run only</div>
                  <div className="mt-1 text-xs font-mono text-taupe">internal-live ≠ third-party-live · status: not sent / handed off manually</div>
                  <div className="mt-1 text-xs font-mono text-taupe">Typed confirmation records what would be handed off. This surface never transmits externally.</div>
                </div>
                <div className="space-y-3 px-3 py-3">
                  <div className="grid gap-3 md:grid-cols-2">
                    <FieldLabel label="Exact recipient">
                      <input className={fieldBase} value={dryRunForm.recipient} onChange={event => updateDryRunField('recipient', event.target.value)} placeholder="recipient@example.com" />
                    </FieldLabel>
                    <FieldLabel label="Exact action proposed">
                      <input className={fieldBase} value={dryRunForm.action} onChange={event => updateDryRunField('action', event.target.value)} placeholder="Would send email / would publish LinkedIn post" />
                    </FieldLabel>
                  </div>
                  <FieldLabel label="Exact payload/body">
                    <textarea className={`${fieldBase} min-h-[7rem] resize-y font-mono text-xs`} value={dryRunForm.payload} onChange={event => updateDryRunField('payload', event.target.value)} placeholder="Paste the exact payload/body that would have been sent." />
                  </FieldLabel>
                  <FieldLabel label={`Typed confirmation: SEND ${dryRunForm.recipient || '<recipient>'}`}>
                    <input className={fieldBase} value={dryRunForm.confirmation} onChange={event => updateDryRunField('confirmation', event.target.value)} placeholder={`SEND ${dryRunForm.recipient || '<recipient>'}`} />
                  </FieldLabel>
                  <div className="flex flex-wrap items-center gap-2">
                    <button type="submit" disabled={dryRunState.submitting} className="inline-flex items-center gap-2 rounded border border-champagne/50 bg-graphite px-3 py-2 text-xs font-mono font-semibold text-champagne transition-colors hover:bg-champagne hover:text-ivory disabled:cursor-not-allowed disabled:opacity-60">
                      {dryRunState.submitting ? 'Writing dry-run receipt...' : 'Confirm dry-run only'}
                    </button>
                    <span className="text-xs font-mono text-taupe">dry_run: true / transmitted: false</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button type="button" onClick={() => copyToClipboard(dryRunForm.recipient)} className="rounded border border-softgraph bg-graphite px-2 py-1 text-xs text-stone">Copy recipient</button>
                    <button type="button" onClick={() => copyToClipboard(dryRunForm.action)} className="rounded border border-softgraph bg-graphite px-2 py-1 text-xs text-stone">Copy action</button>
                    <button type="button" onClick={() => copyToClipboard(dryRunForm.payload)} className="rounded border border-softgraph bg-graphite px-2 py-1 text-xs text-stone">Copy payload</button>
                    {manualPlatformUrl(dryRunForm.action) && <a href={manualPlatformUrl(dryRunForm.action)} target="_blank" rel="noreferrer" className="rounded border border-softgraph bg-graphite px-2 py-1 text-xs text-stone">Open platform manually</a>}
                  </div>
                  {(dryRunState.message || dryRunState.error) && (
                    <div className={`rounded border px-3 py-2 text-xs font-mono ${dryRunState.error ? 'border-clay/40 bg-clay/10 text-clay' : 'border-champagne/30 bg-champagne/10 text-champagne'}`}>
                      {dryRunState.error || `${dryRunState.message}${dryRunState.receiptPath ? ` Receipt: ${dryRunState.receiptPath}` : ''}`}
                    </div>
                  )}
                </div>
              </form>

              <div id="queue-file-preview" className="rounded border border-softgraph bg-ink">
                <div className="flex flex-col gap-2 border-b border-softgraph px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Run / artifacts</div>
                  {hasReceipt && (
                    <div className="break-all text-xs font-mono text-champagne">Latest receipt: {latestReceiptPath}</div>
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
                        {runArtifacts.map((artifact, index) => {
                          const isSelected = filePreview.path === artifact.path
                          const isPrimaryOutput = artifact.path === primaryOutputPath
                          return (
                          <div
                            key={`${artifact.path}-${index}`}
                            role="button"
                            tabIndex={0}
                            onClick={() => viewArtifact(artifact)}
                            onKeyDown={event => {
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault()
                                viewArtifact(artifact)
                              }
                            }}
                            className={`cursor-pointer rounded border px-3 py-2 text-xs font-mono text-stone transition-colors ${
                              isSelected ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-graphite hover:border-taupe'
                            }`}
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <div className="flex flex-wrap gap-2">
                                  {isPrimaryOutput && (
                                    <span className="rounded bg-champagne px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ivory">
                                      Work output / what was done
                                    </span>
                                  )}
                                  {isSelected && (
                                    <span className="rounded border border-champagne/40 px-2 py-0.5 text-[10px] uppercase tracking-wider text-champagne">
                                      Open
                                    </span>
                                  )}
                                </div>
                                <div className="mt-1 break-all text-champagne">{artifact.path}</div>
                                <div className="mt-1 flex flex-wrap gap-2 text-taupe">
                                  <span>{artifactCategory(artifact)}</span>
                                  <span>{artifact.available ? 'readable' : 'unavailable'}</span>
                                  {artifact.size_bytes !== undefined && <span>{artifact.size_bytes} bytes</span>}
                                  {artifact.modified && <span>{artifact.modified}</span>}
                                  {!artifact.available && artifact.reason && <span>{artifact.reason}</span>}
                                </div>
                              </div>
                              <div className="flex flex-shrink-0 flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={event => {
                                    event.stopPropagation()
                                    copyPath(artifact.path)
                                  }}
                                  className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                                >
                                  <Clipboard size={12} />
                                  Copy path
                                </button>
                                <button
                                  type="button"
                                  onClick={event => {
                                    event.stopPropagation()
                                    viewArtifact(artifact)
                                  }}
                                  className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                                >
                                  <FileText size={12} />
                                  View
                                </button>
                              </div>
                            </div>
                          </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="text-sm text-stone">No artifact paths found in the current receipt or work item.</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="rounded border border-softgraph bg-ink">
                <div className="flex flex-col gap-2 border-b border-softgraph px-3 py-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">File preview</div>
                    <div className="mt-1 text-xs font-mono text-taupe">{fileTypeText(filePreview)}</div>
                  </div>
                  {filePreview.path && (
                    <div className="flex flex-wrap gap-2 sm:justify-end">
                      <button
                        type="button"
                        onClick={() => copyPath(filePreview.path)}
                        className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] font-mono text-taupe transition-colors hover:border-champagne hover:text-stone"
                      >
                        <Clipboard size={12} />
                        Copy path
                      </button>
                      <button
                        type="button"
                        onClick={() => setFilePreview({ path: '', category: '', extension: '', loading: false, content: '', error: null })}
                        className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] font-mono text-taupe transition-colors hover:border-champagne hover:text-stone"
                      >
                        Close
                      </button>
                    </div>
                  )}
                </div>
                {filePreview.path ? (
                  <>
                    <div className="border-b border-softgraph px-3 py-2 text-xs font-mono text-champagne break-all">{filePreview.path}</div>
                    {filePreview.loading ? (
                      <div className="px-3 py-5 text-xs font-mono text-taupe">Loading file preview.</div>
                    ) : filePreview.error ? (
                      <div className="px-3 py-5 text-xs font-mono text-clay">{compactReason(filePreview.error)}</div>
                    ) : (
                      <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-5 text-stone">{filePreview.content || 'File is empty.'}</pre>
                    )}
                  </>
                ) : (
                  <div className="px-3 py-5 text-xs font-mono text-taupe">Click any artifact, result, or receipt row to preview it here.</div>
                )}
              </div>

              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Receipt history</div>
                {selected.receipts?.length ? (
                  <div className="mt-2 space-y-2">
                    {selected.receipts.map((receipt, index) => {
                      const path = receiptLabel(receipt)
                      const isSelected = filePreview.path === path
                      return (
                      <div
                        key={`${path}-${index}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => viewReceipt(receipt)}
                        onKeyDown={event => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            viewReceipt(receipt)
                          }
                        }}
                        className={`cursor-pointer rounded border px-3 py-2 text-xs font-mono text-stone transition-colors ${
                          isSelected ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-ink hover:border-taupe'
                        }`}
                      >
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            {isSelected && (
                              <div className="mb-1 inline-flex rounded border border-champagne/40 px-2 py-0.5 text-[10px] uppercase tracking-wider text-champagne">
                                Open
                              </div>
                            )}
                            <div className="break-all">{path}</div>
                          </div>
                          <div className="flex flex-shrink-0 flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={event => {
                                event.stopPropagation()
                                copyPath(path)
                              }}
                              className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                            >
                              <Clipboard size={12} />
                              Copy path
                            </button>
                            <button
                              type="button"
                              onClick={event => {
                                event.stopPropagation()
                                viewReceipt(receipt)
                              }}
                              className="inline-flex items-center gap-2 rounded border border-softgraph px-2 py-1 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone"
                            >
                              <FileText size={12} />
                              View
                            </button>
                          </div>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-2 text-taupe">
                          <span>Receipt</span>
                          {receipt.status && <span>{formatStatus(receipt.status)}</span>}
                          {receipt.created_at && <span>{receipt.created_at}</span>}
                        </div>
                      </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="mt-1 text-sm text-stone">None</div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center text-xs font-mono text-taupe">
              {items.length ? 'Select an item to inspect details.' : 'Queue details will appear when local items exist.'}
            </div>
          )}
        </div>
        )}
      </section>
    </div>
  )
}
