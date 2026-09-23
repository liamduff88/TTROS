import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, ChevronLeft, Clipboard, FileText, Focus, FolderOpen, ListChecks, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { attachQueueReceipt, createQueueItem, deleteQueueItem, externalActionDryRun, getQueueArtifact, getQueueItem, getQueueItemsForScope, getQueuePrompt, getQueueReceipt, getQueueStatus, openQueueArtifactFolder } from '../api'
import { laneColor, laneName, workbenchColor } from '../shellState'
import { artifactKind, detectNoExternalAction, extractRepeatedEntitySummary, parseMarkdownBlocks } from '../artifactPreview'
import {
  canSubmitTaskDeletion,
  classifyArtifact,
  deliverableDisplayLabel,
  groupEntryMatches,
  groupWorkflowChildren,
  loadAccordionState,
  loadPersistedArtifactTabs,
  mergeRefreshedQueueItems,
  persistAccordionState,
  persistArtifactTabs,
  resolveArtifactBaseName,
  resolveArtifactTabTitle,
  resolvePrimaryDeliverable,
  resolveQueueSelection,
  resolveRequestedDeliveryStatus,
  richListOutcomeLine,
  selectionAfterTaskDeletion,
  taskDeletionFailureMessage,
} from '../queueState'
import { isReviewCardItem } from '../reviewCardState'
import { HumanReviewCard } from '../components/HumanReviewCard'
import ArtifactViewer from '../components/ArtifactViewer'

const sessionStore = () => globalThis.sessionStorage
const mainScrollEl = () => document.getElementById('aos-main-scroll')

const QUEUE_STATUSES = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled']
const QUEUE_OWNERS = ['unassigned', 'hermes', 'codex', 'claude', 'revenue', 'marketing', 'delivery', 'operations']
const QUEUE_PRIORITIES = ['low', 'normal', 'high', 'urgent']
const TERMINAL_STATUSES = new Set(['done', 'blocked', 'cancelled'])

const STATUS_PILL_TONE = {
  done: 'border-champagne bg-champagne text-ivory',
  blocked: 'border-clay/50 bg-clay/10 text-clay',
  cancelled: 'border-softgraph bg-well text-taupe',
  human_review: 'border-champagne/40 bg-champagne/10 text-champagne',
  needs_input: 'border-champagne/40 bg-champagne/10 text-champagne',
  agent_working: 'border-softgraph bg-ink text-stone',
}
const DEFAULT_STATUS_PILL_TONE = 'border-softgraph bg-ink text-taupe'

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

const REVIEW_OR_COMPLETE_STATUSES = new Set(['human_review', 'done', 'blocked', 'needs_input'])

const itemLane = item => item?.lane || item?.owner || 'unassigned'

const NEEDS_ME_STATUSES = new Set(['human_review', 'needs_input', 'blocked'])

const matchesFilters = (item, filters) =>
  (!filters.needsMe || NEEDS_ME_STATUSES.has(item.status) || (Array.isArray(item.needs_me) && item.needs_me.length > 0)) &&
  (!filters.status || item.status === filters.status) &&
  (!filters.workbench || item.owner === filters.workbench) &&
  (!filters.lane || itemLane(item) === filters.lane) &&
  (!filters.source || String(item.source || '').toLowerCase() === String(filters.source).toLowerCase())

const relativeAge = value => {
  const time = Date.parse(value || '')
  if (Number.isNaN(time)) return 'unknown age'
  const minutes = Math.max(0, Math.round((Date.now() - time) / 60000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

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

const emptyAnswerState = { submitting: false, answer: '', message: '', error: null }
const emptyDryRunForm = { recipient: '', action: '', payload: '', confirmation: '' }
const emptyDryRunState = { submitting: false, message: '', error: null, receiptPath: '' }
const emptyDeletionState = { open: false, itemId: '', title: '', expectedHash: '', reason: '', confirmation: '', requestId: '', submitting: false }

const newDeletionRequestId = () => {
  const random = globalThis.crypto?.randomUUID?.().replace(/-/g, '') || `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`
  return `delete-${random}`
}

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

const StatusPill = ({ status }) => (
  <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wide ${STATUS_PILL_TONE[status] || DEFAULT_STATUS_PILL_TONE}`}>
    {formatStatus(status) || 'unknown'}
  </span>
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
  const [nextItem, setNextItem] = useState(null)
  const [selectedId, setSelectedId] = useState(initialSelectedId)
  const [filters, setFilters] = useState(filtersFromParams(initialFilters))
  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [createState, setCreateState] = useState({ submitting: false, message: '', error: null })
  const [promptCopy, setPromptCopy] = useState({ target: null, message: '', error: null })
  const [runState, setRunState] = useState({ running: false, result: null, error: null })
  const [answerState, setAnswerState] = useState(emptyAnswerState)
  const [receiptPreviewExpanded, setReceiptPreviewExpanded] = useState(false)
  const [dryRunForm, setDryRunForm] = useState(emptyDryRunForm)
  const [dryRunState, setDryRunState] = useState(emptyDryRunState)
  const [deletionState, setDeletionState] = useState(emptyDeletionState)
  const [deletionNotice, setDeletionNotice] = useState({ message: '', error: null })
  const [finalStepSelection, setFinalStepSelection] = useState({ targetId: '', message: '' })
  const [focusMode, setFocusMode] = useState(false)
  const [listCollapsed, setListCollapsed] = useState(Boolean(initialSelectedId))
  const [restoredTabState] = useState(() => loadPersistedArtifactTabs(sessionStore()))
  const [artifactTabs, setArtifactTabs] = useState(() => restoredTabState.tabs.map(tab => ({
    ...tab, loading: true, content: '', error: null, isBinary: false, contentType: '',
  })))
  const [activeContentTab, setActiveContentTab] = useState(restoredTabState.activeContentTab)
  const [accordionState, setAccordionState] = useState(() => loadAccordionState(sessionStore(), initialSelectedId))
  const [primaryPreview, setPrimaryPreview] = useState({ path: '', highlights: null, noExternalAction: false })
  const selectedDetailRef = useRef(null)
  const listPanelRef = useRef(null)
  const listScrollRef = useRef(0)
  // True only while the operator has deliberately tapped "Back to Work
  // Queue" on mobile to browse the list with nothing selected. Distinct from
  // selectedId simply being empty on load/after a delete, which the existing
  // auto-reselect effects below should keep filling in as before.
  const browsingListRef = useRef(false)
  const selectedIdRef = useRef(initialSelectedId)
  const selectionRevisionRef = useRef(0)
  const refreshRequestRef = useRef(0)
  const detailRequestRef = useRef(0)
  const deletionSubmittingRef = useRef(false)
  const itemsRef = useRef(items)
  const artifactTabsRef = useRef(artifactTabs)
  const scrollMemoryRef = useRef({})
  const [state, setState] = useState({ loading: true, error: null })

  useEffect(() => { itemsRef.current = items }, [items])
  useEffect(() => { artifactTabsRef.current = artifactTabs }, [artifactTabs])

  // Persist open tabs + the active tab (never raw content) so they survive a
  // navigation away to another dashboard page and back, and — best-effort — a
  // hard reload, the same way the Ask David thread persists via sessionStorage.
  useEffect(() => {
    persistArtifactTabs(sessionStore(), artifactTabs, activeContentTab)
  }, [artifactTabs, activeContentTab])

  // Restore the content for whatever tabs came back from sessionStorage.
  // Runs once: fetchTabContent is stable enough for a mount-only refetch since
  // it only touches setArtifactTabs, and re-running it on every tabs change
  // would refetch on every open/close.
  useEffect(() => {
    restoredTabState.tabs.forEach(tab => {
      fetchTabContent(tab.id, tab.path, tab.category === 'Receipt')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Restores the remembered scroll position (Overview or a given artifact
  // tab's own reading position) whenever the visible content tab changes,
  // instead of leaving whatever position the browser happened to clamp
  // scrollTop to once the previous content's height changed.
  useEffect(() => {
    const container = mainScrollEl()
    if (!container) return
    const target = scrollMemoryRef.current[activeContentTab] || 0
    const raf = window.requestAnimationFrame(() => { container.scrollTop = target })
    return () => window.cancelAnimationFrame(raf)
  }, [activeContentTab])

  const switchContentTab = next => {
    const container = mainScrollEl()
    if (container) scrollMemoryRef.current[activeContentTab] = container.scrollTop
    setActiveContentTab(next)
  }

  const updateAccordion = (key, value) => {
    setAccordionState(current => {
      const next = { ...current, [key]: value }
      persistAccordionState(sessionStore(), selectedIdRef.current, next)
      return next
    })
  }

  // A parent objective + its execution child step render as one top-level
  // entry (F-QUEUE-GROUPING) instead of two visually equivalent peer jobs;
  // grouping happens before filtering so a filter chip a folded child alone
  // matches still surfaces its parent's card.
  const groupedItems = useMemo(() => groupWorkflowChildren(items), [items])
  const filteredItems = useMemo(
    () => groupedItems.filter(item => groupEntryMatches(item, row => matchesFilters(row, filters))),
    [groupedItems, filters],
  )
  const selected = useMemo(
    () => items.find(item => item.id === selectedId) || null,
    [items, selectedId],
  )
  const selectedStatus = selected?.status || ''
  const isTerminalStatus = TERMINAL_STATUSES.has(selectedStatus)
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
    : isTerminalStatus
      ? 'Run again'
      : hasReceipt || isReviewOrComplete
        ? 'Rerun assigned worker'
        : 'Run assigned worker'

  const selectQueueItem = (id, notify = true) => {
    if (deletionState.open && deletionState.itemId !== id) setDeletionState(emptyDeletionState)
    // Below md, selecting an item hides the list entirely (see the column
    // wrappers below); remember its scroll offset so "Back to Work Queue"
    // restores the exact list position instead of resetting to the top.
    if (id && !selectedIdRef.current) {
      const scrollEl = mainScrollEl()
      if (scrollEl) listScrollRef.current = scrollEl.scrollTop
    }
    if (id) browsingListRef.current = false
    selectedIdRef.current = id
    selectionRevisionRef.current += 1
    setSelectedId(id)
    if (id && notify) setListCollapsed(true)
    if (notify) onViewParamsChange?.({ ...filters, selectedId: id })
    if (!id) {
      window.requestAnimationFrame(() => {
        const scrollEl = mainScrollEl()
        if (scrollEl) scrollEl.scrollTop = listScrollRef.current
        listPanelRef.current?.focus()
      })
    }
  }

  // Mobile "Back to Work Queue": unlike selectQueueItem(null) (used by the
  // auto-reselect fallbacks below, which always want *something* selected),
  // this is a deliberate choice to browse the list with nothing selected,
  // and must survive the next background refresh instead of being
  // immediately re-filled by resolveQueueSelection.
  const goToList = () => {
    browsingListRef.current = true
    selectQueueItem(null)
  }

  const refreshQueue = async (preferredId = null) => {
    const requestId = ++refreshRequestRef.current
    const selectionRevision = selectionRevisionRef.current
    setState(current => ({ loading: !current.error && current.loading, error: current.error }))
    try {
      const [statusData, itemsData] = await Promise.all([getQueueStatus(), getQueueItemsForScope('all')])
      if (statusData?.success === false || itemsData?.success === false) {
        throw new Error(statusData?.reason || itemsData?.reason || 'Queue unavailable')
      }

      const fresh = itemsData?.items || []
      const next = statusData?.nextItem || null
      if (requestId !== refreshRequestRef.current) return
      // Merge before sorting: a compact background-refresh row must not overwrite
      // an already-loaded rich row (see mergeRefreshedQueueItems for why).
      const list = sortQueueItemsNewestFirst(mergeRefreshedQueueItems(itemsRef.current, fresh))
      // A deliberate "Back to Work Queue" tap (browsingListRef) must survive
      // a background refresh instead of resolveQueueSelection immediately
      // refilling it with whatever item is next up.
      const resolvedId = browsingListRef.current ? null : resolveQueueSelection({
        items: list,
        currentId: selectedIdRef.current,
        preferredId,
        nextId: next?.id,
        selectionChanged: selectionRevisionRef.current !== selectionRevision,
      })
      setStatus(statusData)
      setItems(list)
      itemsRef.current = list
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

  const refreshQueueRef = useRef(refreshQueue)
  useEffect(() => { refreshQueueRef.current = refreshQueue })

  useEffect(() => {
    refreshQueue()
    // A ref-based indirection keeps the interval calling the *latest* refreshQueue
    // closure (current filters/state) instead of the one captured at mount, which
    // previously let a stale background poll silently overwrite a filter the
    // operator had since changed.
    const poll = window.setInterval(() => refreshQueueRef.current(selectedIdRef.current), 5000)
    return () => window.clearInterval(poll)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedId) setListCollapsed(true)
  }, [selectedId])

  useEffect(() => {
    const item = items.find(row => row.id === selectedId)
    if (!selectedId || !item || item.detail_loaded) return
    const requestId = ++detailRequestRef.current
    getQueueItem(selectedId)
      .then(data => {
        if (requestId !== detailRequestRef.current || data?.success === false || !data?.item) return
        setItems(current => current.map(row => row.id === selectedId ? { ...row, ...data.item } : row))
      })
      .catch(error => {
        if (requestId === detailRequestRef.current) setState(current => ({ ...current, error }))
      })
  }, [selectedId, items])

  useEffect(() => {
    const explicitSelectedId = selectedIdFromParams(initialFilters)
    setFilters(filtersFromParams(initialFilters))
    if (explicitSelectedId && explicitSelectedId !== selectedIdRef.current) selectQueueItem(explicitSelectedId, false)
  }, [JSON.stringify(initialFilters)])

  useEffect(() => {
    if (state.loading || !items.length || browsingListRef.current) return
    // A selected item is still "visible" if it's a top-level filtered row OR
    // a step folded into one of those rows by grouping (F-QUEUE-GROUPING) —
    // otherwise selecting a folded child step would immediately bounce back
    // to its parent, since the child never appears as a top-level id here.
    if (filteredItems.some(item => item.id === selectedId || item.childSteps?.some(child => child.id === selectedId))) return
    selectQueueItem(filteredItems[0]?.id || null)
  }, [filteredItems, state.loading, selectedId])

  useEffect(() => {
    setRunState({ running: false, result: null, error: null })
    setAnswerState(emptyAnswerState)
    setReceiptPreviewExpanded(false)
    setDryRunForm(emptyDryRunForm)
    setDryRunState(emptyDryRunState)
  }, [selectedId])

  // Workflow / Technical details / Receipts accordion state is keyed by work
  // item ID and reloaded (not reset) whenever the selection changes, so
  // reopening an item — including after navigating away to Cockpit/another
  // page and back — restores exactly the sections that item had expanded.
  useEffect(() => {
    setAccordionState(loadAccordionState(sessionStore(), selectedId))
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

  // --- Internal artifact/receipt tabs -------------------------------------
  // Opens a receipt or artifact inside the Work Queue's own content area
  // (never a filesystem path or a new browser tab). Re-opening an already
  // open tab just focuses it instead of refetching.
  const fetchTabContent = async (tabId, path, isReceipt) => {
    try {
      const response = isReceipt ? await getQueueReceipt(path) : await getQueueArtifact(path)
      if (response?.success === false) throw new Error(response?.reason || response?.message || 'Preview unavailable')
      setArtifactTabs(current => current.map(tab => tab.id === tabId ? {
        ...tab,
        loading: false,
        error: null,
        content: response.content || '',
        isBinary: Boolean(response.is_binary),
        contentType: response.content_type || '',
        extension: response.extension || tab.extension,
        path: response.path || tab.path,
      } : tab))
    } catch (error) {
      setArtifactTabs(current => current.map(tab => tab.id === tabId ? {
        ...tab,
        loading: false,
        error: error?.response?.data?.detail || error?.message || 'Preview failed',
      } : tab))
    }
  }

  const openArtifactTab = (ref, { isReceipt = false } = {}) => {
    const path = ref?.path
    if (!path) return
    switchContentTab(path)
    if (artifactTabsRef.current.some(tab => tab.id === path)) return
    const available = ref?.available !== false
    const classification = classifyArtifact(ref)
    const newTab = {
      id: path,
      path,
      label: resolveArtifactTabTitle({ ref, queueItemTitle: selected?.title, classification }),
      category: ref?.category || (isReceipt ? 'Receipt' : 'Artifact'),
      extension: ref?.extension || (path.includes('.') ? `.${path.split('.').pop().toLowerCase()}` : ''),
      loading: available,
      content: '',
      error: available ? null : (ref?.reason || 'File is listed but is not available to preview.'),
      isBinary: false,
      contentType: '',
    }
    setArtifactTabs(current => [...current, newTab])
    if (available) fetchTabContent(path, path, isReceipt)
  }

  const closeArtifactTab = tabId => {
    setArtifactTabs(current => current.filter(tab => tab.id !== tabId))
    if (activeContentTab === tabId) switchContentTab('overview')
  }

  const viewReceipt = receipt => openArtifactTab({
    path: receiptLabel(receipt),
    category: 'Receipt',
    extension: '.md',
    name: receiptLabel(receipt).split('/').pop(),
  }, { isReceipt: true })

  const viewArtifact = artifact => openArtifactTab({
    path: artifact?.path,
    category: artifactCategory(artifact),
    extension: artifact?.extension,
    name: artifact?.name,
    available: artifact?.available,
    reason: artifact?.reason,
  })

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
      refresh?.()
    } catch (error) {
      setRunState({
        running: false,
        result: null,
        error: error?.message || 'Queue item run failed',
      })
    }
  }

  const updateAnswerText = value => {
    setAnswerState(current => ({ ...current, answer: value, message: '', error: null }))
  }

  const submitNeedsInputAnswer = async () => {
    if (!selected?.id || selected.status !== 'needs_input' || answerState.submitting) return
    const answer = answerState.answer.trim()
    if (!answer) {
      setAnswerState(current => ({ ...current, message: '', error: 'An answer is required to resume this item.' }))
      return
    }
    setAnswerState(current => ({ ...current, submitting: true, message: '', error: null }))
    try {
      const response = await attachQueueReceipt(selected.id, {
        receipt_text: `Operator answer:\n${answer}`,
        status: 'agent_todo',
      })
      if (response?.success === false || response?.ok === false) {
        throw new Error(response?.reason || response?.message || 'Answer failed to save')
      }
      await refreshQueue(selected.id)
      refresh?.()
      setAnswerState({ submitting: false, answer: '', message: 'Answer saved; item resumed to agent_todo.', error: null })
    } catch (error) {
      setAnswerState(current => ({
        ...current,
        submitting: false,
        message: '',
        error: error?.response?.data?.detail || error?.message || 'Answer failed to save',
      }))
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
      refresh?.()
      setDryRunState({ submitting: false, message: 'Dry-run receipt written. No external transmission occurred.', error: null, receiptPath: response.receipt_path || '' })
    } catch (error) {
      setDryRunState({ submitting: false, message: '', error: error?.response?.data?.detail || error?.message || 'Dry-run confirmation failed', receiptPath: '' })
    }
  }

  const openTaskDeletion = () => {
    if (!selected?.id) return
    setDeletionNotice({ message: '', error: null })
    setDeletionState({
      open: true,
      itemId: selected.id,
      title: selected.title || 'Untitled queue item',
      expectedHash: selected.record_hash || '',
      reason: '',
      confirmation: '',
      requestId: newDeletionRequestId(),
      submitting: false,
    })
  }

  const cancelTaskDeletion = () => {
    if (deletionSubmittingRef.current) return
    setDeletionState(emptyDeletionState)
  }

  const submitTaskDeletion = async event => {
    event.preventDefault()
    if (deletionSubmittingRef.current || !canSubmitTaskDeletion({
      itemId: deletionState.itemId,
      reason: deletionState.reason,
      confirmation: deletionState.confirmation,
      submitting: deletionState.submitting,
    })) return
    if (!deletionState.expectedHash) {
      setDeletionNotice({ message: '', error: 'This item has no deletion version. Refresh the queue and try again.' })
      return
    }

    deletionSubmittingRef.current = true
    setDeletionState(current => ({ ...current, submitting: true }))
    setDeletionNotice({ message: '', error: null })
    try {
      const response = await deleteQueueItem(deletionState.itemId, {
        expected_record_hash: deletionState.expectedHash,
        deletion_reason: deletionState.reason.trim(),
        request_id: deletionState.requestId,
      })
      if (response?.success === false || response?.ok === false || response?.deleted_item_id !== deletionState.itemId) {
        throw new Error(response?.reason || response?.message || 'Task deletion did not return a valid result')
      }

      const deletedId = deletionState.itemId
      const next = selectionAfterTaskDeletion(items, deletedId)
      setItems(next.items)
      selectedIdRef.current = next.selectedId
      setSelectedId(next.selectedId)
      setNextItem(current => current?.id === deletedId ? (next.items.find(item => !['done', 'cancelled'].includes(item.status)) || null) : current)
      setStatus(current => current ? {
        ...current,
        counts: response.counts || current.counts,
        totalCount: response.total_count ?? Math.max(0, (current.totalCount || items.length) - 1),
        activeCount: Object.entries(response.counts || {}).reduce((total, [queueStatus, value]) => total + (!['done', 'cancelled'].includes(queueStatus) ? Number(value) || 0 : 0), 0),
      } : current)
      onViewParamsChange?.({ ...filters, selectedId: next.selectedId })
      setDeletionState(emptyDeletionState)
      setDeletionNotice({
        message: `${deletedId} was permanently removed. Minimal tombstone: ${response.tombstone_reference}.`,
        error: null,
      })
      await refreshQueue(next.selectedId)
      await refresh?.()
    } catch (error) {
      const detail = error?.response?.data?.detail
      setDeletionState(current => ({ ...current, submitting: false }))
      setDeletionNotice({
        message: '',
        error: taskDeletionFailureMessage(detail || error?.message),
      })
    } finally {
      deletionSubmittingRef.current = false
    }
  }

  const reason = state.error?.response?.data?.detail || state.error?.message
  const counts = status?.counts || {}
  const activeCount = status?.activeCount ?? items.filter(item => !['done', 'cancelled'].includes(item.status)).length
  const totalCount = status?.totalCount ?? Object.values(counts).reduce((total, value) => total + (Number(value) || 0), 0)
  const needsLiam = status?.needsLiam ?? ((counts.needs_input || 0) + (counts.human_review || 0) + (counts.blocked || 0))
  const latestReceiptPath = receiptLabel(latestReceipt)
  const primaryArtifact = selected?.primary_artifact || null
  const finalArtifact = finalResult?.final_artifacts?.find(artifact => artifact.available) || (finalResult?.final_artifact_paths?.[0] ? { path: finalResult.final_artifact_paths[0], available: true, category: 'Final review package', extension: '.md' } : null)
  const finalReceipt = finalResult?.final_receipts?.find(receipt => receipt.available) || (finalResult?.final_receipt_paths?.[0] ? { path: finalResult.final_receipt_paths[0], available: true, category: 'Final receipt', extension: '.md' } : null)
  const finalStepSelectionMessage = finalStepSelection.targetId && finalStepSelection.targetId === selected?.id ? finalStepSelection.message : ''
  const deliverable = useMemo(
    () => resolvePrimaryDeliverable({ finalArtifact, primaryArtifact, runArtifacts, latestReceiptPath }),
    [finalArtifact, primaryArtifact, runArtifacts, latestReceiptPath],
  )
  const requestedDelivery = useMemo(() => selected ? resolveRequestedDeliveryStatus(selected) : null, [selected])

  // Concise result preview on the overview (F-RESULT-HIGHLIGHTS): when the
  // primary deliverable is markdown, generically extract a repeated numbered
  // section (e.g. "5 selected outreach candidates") and no-external-action
  // state, instead of hard-coding parsing for one workflow's report shape.
  useEffect(() => {
    const primary = deliverable.primary
    if (!primary?.path || artifactKind(primary.extension) !== 'markdown') {
      setPrimaryPreview({ path: '', highlights: null, noExternalAction: false })
      return
    }
    let cancelled = false
    const applyContent = content => {
      if (cancelled) return
      const blocks = parseMarkdownBlocks(content || '')
      setPrimaryPreview({
        path: primary.path,
        highlights: extractRepeatedEntitySummary(blocks),
        noExternalAction: detectNoExternalAction(content || ''),
      })
    }
    const preloaded = selected?.primary_artifact?.path === primary.path ? selected.primary_artifact.content : null
    if (preloaded) {
      applyContent(preloaded)
    } else {
      getQueueArtifact(primary.path).then(response => {
        if (!cancelled && response?.success !== false) applyContent(response.content)
      }).catch(() => {})
    }
    return () => { cancelled = true }
  }, [deliverable.primary?.path, selected?.id])

  const openFinalFolder = async () => {
    if (!finalArtifact?.path) return
    try {
      await openQueueArtifactFolder(finalArtifact.path)
    } catch (error) {
      openArtifactTab({ path: finalArtifact.path, category: 'Output folder', available: false, reason: error?.response?.data?.detail || error?.message || 'Output folder open failed' })
    }
  }

  const viewFinalStep = () => {
    const finalItemId = finalResult?.final_item_id
    if (!finalItemId) return
    setFilters({})
    switchContentTab('overview')
    selectQueueItem(finalItemId)
    setFinalStepSelection({ targetId: finalItemId, message: 'Final step selected' })
  }

  const activeArtifactTab = artifactTabs.find(tab => tab.id === activeContentTab) || null

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

      {/* Tab bar + its content panel are a single flex-col block with no gap
          between them, so the two form one visual seam instead of the
          space-y-5 rhythm's usual gap (BUILD_SPECIFICATION "sticky tab bar
          and content panel share one border seam ... zero margin/gap"). */}
      <div className="flex flex-col">
      {/* #aos-main-scroll (the real scrolling ancestor) now carries no padding
          of its own — page padding lives in App.jsx's inner wrapper instead —
          so `top-0` pins this bar flush against the scrollport top with no
          blank gap above it once it sticks (BUILD_SPECIFICATION "Sticky
          geometry and responsive behavior"). */}
      <div
        className="sticky top-0 z-20 flex items-center gap-1 overflow-x-auto rounded-t border border-b-0 border-softgraph bg-graphite px-1 pt-1"
        role="tablist"
        aria-label="Work queue content tabs"
        data-testid="queue-content-tabs"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeContentTab === 'overview'}
          onClick={() => switchContentTab('overview')}
          className={`shrink-0 rounded-t px-3 py-2 text-xs font-mono transition-colors ${activeContentTab === 'overview' ? 'bg-ink text-ivory' : 'text-taupe hover:text-stone'}`}
        >
          Work Queue
        </button>
        {artifactTabs.map(tab => (
          <div
            key={tab.id}
            role="tab"
            aria-selected={activeContentTab === tab.id}
            data-testid="artifact-tab"
            className={`group flex shrink-0 items-center gap-1 rounded-t px-1 py-1 ${activeContentTab === tab.id ? 'bg-ink text-ivory' : 'text-taupe hover:text-stone'}`}
          >
            <button type="button" onClick={() => switchContentTab(tab.id)} className="max-w-40 truncate px-2 py-1 text-left text-xs font-mono" title={tab.label}>
              {tab.label}
            </button>
            <button type="button" onClick={() => closeArtifactTab(tab.id)} aria-label={`Close ${tab.label}`} className="rounded p-1.5 text-taupe hover:bg-well hover:text-ivory">
              <X size={12} />
            </button>
          </div>
        ))}
      </div>

      {activeContentTab !== 'overview' ? (
        <div className="flex min-h-[70vh] flex-col gap-3 rounded-b-lg border border-t-0 border-softgraph bg-graphite p-3">
          <button
            type="button"
            onClick={() => switchContentTab('overview')}
            className="inline-flex w-fit items-center gap-1.5 rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone hover:border-champagne"
          >
            <ChevronLeft size={13} />Back to Work Queue
          </button>
          <ArtifactViewer tab={activeArtifactTab} onCopyPath={copyPath} />
        </div>
      ) : (
      <div className="space-y-5 pt-4">
      {state.error && (
        <div className="rounded-lg border border-clay/40 bg-clay/10 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-stone">
            <AlertCircle size={15} className="text-clay" />
            Queue load failed
          </div>
          <div className="mt-2 text-xs font-mono text-taupe">{compactReason(reason)}</div>
        </div>
      )}

      {(deletionNotice.message || deletionNotice.error) && (
        <div
          className={`rounded-lg border p-4 text-xs font-mono ${deletionNotice.error ? 'border-clay/40 bg-clay/10 text-clay' : 'border-champagne/30 bg-champagne/10 text-champagne'}`}
          role={deletionNotice.error ? 'alert' : 'status'}
          data-testid="task-deletion-notice"
        >
          {deletionNotice.error || deletionNotice.message}
        </div>
      )}

      {status ? <section className="rounded-lg border border-softgraph bg-graphite p-5">
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
      </section> : state.loading ? (
        <div className="rounded-lg border border-softgraph bg-graphite p-5 text-xs font-mono text-taupe">Loading real queue counts…</div>
      ) : null}

      {focusMode && (
        <div className="flex gap-1 overflow-x-auto rounded border border-softgraph bg-graphite p-2" data-testid="focus-mini-rail">
          {filteredItems.filter(item => item.id !== selectedId).map(item => (
            <button key={item.id} onClick={() => selectQueueItem(item.id)} className="relative flex h-9 max-w-56 shrink-0 items-center gap-2 overflow-hidden rounded border border-softgraph bg-ink pl-3 pr-2 text-[10px] text-stone" aria-label={`Focus ${item.title || 'Untitled task'} (${item.id})`} title={`${item.title || 'Untitled task'} · ${item.id}`}>
              <span className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: workbenchColor(item.invocation_source, item.status) }} />
              <span className="truncate font-semibold">{item.title || 'Untitled task'}</span><span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: workbenchColor(item.invocation_source, item.status) }} />
            </button>
          ))}
        </div>
      )}

      <section className={`grid gap-4 ${focusMode ? 'grid-cols-1' : listCollapsed ? 'lg:grid-cols-[10rem_minmax(0,1fr)]' : 'lg:grid-cols-[minmax(22rem,0.9fr)_minmax(0,1.1fr)]'}`} data-list-collapsed={listCollapsed ? 'true' : 'false'}>
        {/* Below md (768px) the list and the selected item are mutually
            exclusive full-width panels, never squeezed side by side
            (BUILD_SPECIFICATION "Queue uses list → full-width detail"). At
            md and up this column always shows; the lg: grid above then adds
            the real master/detail split. */}
        <div className={`space-y-4 ${focusMode ? 'hidden' : selected ? 'hidden md:block' : ''}`}>
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

          <div ref={listPanelRef} tabIndex={-1} className={`rounded-lg border ${filters.needsMe ? 'border-champagne/40' : 'border-softgraph'} bg-graphite ${listCollapsed ? 'p-2' : 'p-5'} focus:outline-none`} data-testid="queue-list-panel">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ListChecks size={14} className={filters.needsMe ? 'text-champagne' : 'text-taupe'} />
                <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">
                  {listCollapsed ? 'Queue' : filters.needsMe ? 'Needs Me — human review & needs input, newest first' : 'Work items'}
                </h2>
              </div>
              <div className={`items-center gap-2 ${listCollapsed ? 'hidden' : 'flex'}`}>
                {filters.needsMe
                  ? <button type="button" onClick={() => setFilters({})} className="inline-flex items-center gap-1.5 rounded border border-champagne/40 bg-champagne/10 px-2 py-1 text-[11px] font-mono text-champagne transition-colors hover:bg-champagne/20">Needs Me (press /) ×</button>
                  : <QueueFilterChip filters={filters} onClear={() => setFilters({})} />}
                <div className="font-mono text-xs text-taupe">{filteredItems.length} of {items.length}</div>
              </div>
            </div>

            {state.loading && !items.length ? (
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
                    {listCollapsed ? (
                      <div>
                        <div className="truncate text-[11px] font-semibold text-stone">{item.title || 'Untitled task'}</div>
                        <div className="mt-0.5 truncate font-mono text-[9px] text-taupe">{item.id || 'No ID'}</div>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 truncate text-sm font-semibold text-ivory">{item.title || 'Untitled queue item'}</div>
                          {(nextItem?.id === item.id || item.childSteps?.some(child => child.id === nextItem?.id)) && <CheckCircle2 size={14} className="mt-1 flex-shrink-0 text-champagne" />}
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2">
                          <StatusPill status={item.status} />
                          <span className="font-mono text-[11px] text-taupe">{relativeAge(item.updated_at || item.created_at)}</span>
                          {item.childSteps?.length > 0 && (
                            <span className="rounded border border-softgraph px-1.5 py-0.5 text-[10px] font-mono text-taupe" title="Execution steps folded into this workflow">
                              {item.childSteps.length + 1} steps
                            </span>
                          )}
                        </div>
                        {richListOutcomeLine(item) && (
                          <div className="mt-1.5 line-clamp-2 text-xs leading-5 text-stone">{richListOutcomeLine(item)}</div>
                        )}
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 font-mono text-[10px] text-taupe">
                          <span>{item.id || 'No ID'}</span>
                          <span className="rounded px-1.5 py-0.5 font-bold text-white" style={{ backgroundColor: laneColor(laneName(item)) }}>{laneName(item)}</span>
                          <span>{item.owner || 'unassigned'}</span>
                          {item.source && <span>{item.source}</span>}
                        </div>
                        {Array.isArray(item.needs_me) && item.needs_me.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {item.needs_me.map(needReason => <span key={needReason} className="rounded border border-champagne/50 bg-champagne/10 px-1.5 py-0.5 text-[10px] text-champagne">{needReason}</span>)}
                          </div>
                        )}
                      </>
                    )}
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
                <div className="text-sm font-semibold text-stone">No queue items found.</div>
              </div>
            )}
          </div>
        </div>

        {/* Symmetric with the list column above: hidden on mobile until
            something is selected, always visible at md+ where both panels
            already coexist as a master/detail pair. */}
        <div className={`space-y-3 ${selected ? '' : 'hidden md:block'}`}>
        {selected && (
          <button
            type="button"
            onClick={goToList}
            className="inline-flex items-center gap-1.5 rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone hover:border-champagne md:hidden"
            data-testid="queue-back-to-list"
          >
            <ChevronLeft size={13} />Back to Work Queue
          </button>
        )}
        {selected && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-softgraph bg-graphite px-4 py-3" data-testid="task-deletion-control">
            <div className="min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Selected task safety</div>
              <div className="mt-1 truncate text-xs font-mono text-stone">{selected.id} — permanent removal requires confirmation</div>
            </div>
            <button
              type="button"
              onClick={openTaskDeletion}
              className="inline-flex flex-shrink-0 items-center gap-2 rounded border border-clay/40 bg-ink px-3 py-2 text-xs font-mono text-clay transition-colors hover:border-clay hover:bg-clay/10"
              data-testid="open-task-deletion"
            >
              <Trash2 size={13} />Delete
            </button>
          </div>
        )}
        {selected && isReviewCardItem(selected) ? (
          <HumanReviewCard
            item={selected}
            className="self-start"
            onOpenArtifact={ref => openArtifactTab(ref, { isReceipt: ref?.category === 'Receipt' })}
            onSaved={async () => {
              await refreshQueue(selected.id)
              await refresh?.()
            }}
          />
        ) : (
        <div id="queue-selected-detail" ref={selectedDetailRef} className="scroll-landing rounded-lg border bg-graphite p-5" style={{ borderColor: selected ? workbenchColor(selected.invocation_source, selected.status) : 'var(--hairline)' }} data-testid="queue-selected-detail" data-selected-item-id={selected?.id || ''} data-invocation-source={selected?.invocation_source || 'unattributed'}>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Selected item</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-base font-semibold text-ivory">{selected ? selected.title || 'Untitled task' : 'No item selected'}</span>
                {selected && <span className="font-mono text-[10px] text-taupe">{selected.id}</span>}
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
                <button
                  type="button"
                  onClick={runAssignedWorker}
                  disabled={runState.running || (isWorkerRunning && !isStuckWorker)}
                  className={isTerminalStatus
                    ? 'inline-flex items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-taupe transition-colors hover:border-champagne hover:text-stone disabled:cursor-not-allowed disabled:opacity-60'
                    : 'inline-flex items-center gap-2 rounded bg-champagne px-3 py-2 text-xs font-mono font-semibold text-ivory transition-colors hover:bg-well disabled:cursor-not-allowed disabled:opacity-60'}
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

              {/* A. Title + real status */}
              <div>
                <div className="text-xl font-semibold text-ivory">{selected.title || 'Untitled queue item'}</div>
                <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-xs text-taupe">
                  <StatusPill status={selected.status} />
                  {selected.honest_status && selected.honest_status !== selected.status && <span>({formatStatus(selected.honest_status)})</span>}
                  {selected.step_progress?.label && <span>{selected.step_progress.label}</span>}
                  <span>{selected.owner || 'unassigned'}</span>
                  <span>Priority {selected.priority ?? 0}</span>
                </div>
                {hasProducedArtifact && (
                  <div className="mt-3 rounded border border-champagne/30 bg-champagne/10 px-3 py-2 text-xs font-mono text-champagne">
                    human review: produced artifact available below
                  </div>
                )}
                {/* Only rendered when the item's own recorded request text names a
                    delivery channel (e.g. "send me a Telegram message with the
                    file attached") — never fabricated for an item that never
                    asked for delivery (F-DELIVERY-EVIDENCE). */}
                {requestedDelivery && (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2" data-testid="requested-delivery-status">
                    <div className="rounded border border-softgraph bg-ink px-3 py-2">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-taupe">Work result</div>
                      <div className="mt-0.5 text-xs font-mono text-stone">{isTerminalStatus ? formatStatus(selectedStatus) : 'in progress'}</div>
                    </div>
                    <div className={`rounded border px-3 py-2 ${requestedDelivery.completed ? 'border-softgraph bg-ink' : 'border-clay/40 bg-clay/10'}`}>
                      <div className={`text-[10px] font-semibold uppercase tracking-wider ${requestedDelivery.completed ? 'text-taupe' : 'text-clay'}`}>
                        Requested delivery ({requestedDelivery.channel})
                      </div>
                      <div className={`mt-0.5 text-xs font-mono ${requestedDelivery.completed ? 'text-stone' : 'text-clay'}`}>
                        {requestedDelivery.completed ? 'completed' : 'not completed / no evidence of completion'}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* B. Operator outcome / summary — "what happened" */}
              <div className="rounded border border-softgraph bg-ink p-4">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">What happened</div>
                <p className="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-stone">
                  {selected.summary_for_operator || latestReceipt?.summary || (isWorkerRunning ? 'Worker is running; refresh for status.' : 'No outcome summary recorded yet.')}
                </p>
              </div>

              {/* C. Primary result / deliverable */}
              {deliverable.primary ? (
                <div className="rounded border border-champagne/40 bg-champagne/5 p-4" data-testid="primary-result">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-champagne">Primary result</div>
                  <div className="mt-1 break-all text-sm text-stone">{deliverableDisplayLabel(deliverable.primary, { queueItemTitle: selected.title })}</div>
                  {primaryPreview.path === deliverable.primary.path && (primaryPreview.highlights || primaryPreview.noExternalAction) && (
                    <div className="mt-2 rounded border border-softgraph bg-ink px-3 py-2 text-xs text-stone" data-testid="primary-result-highlights">
                      {primaryPreview.highlights && (
                        <div>
                          <span className="font-semibold text-champagne">{primaryPreview.highlights.count} selected</span>
                          {' — '}{primaryPreview.highlights.names.join(' · ')}
                        </div>
                      )}
                      {primaryPreview.noExternalAction && <div className={primaryPreview.highlights ? 'mt-1 text-taupe' : 'text-taupe'}>No external action was taken.</div>}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => viewArtifact(deliverable.primary)}
                    className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded bg-champagne px-4 py-3 text-center text-sm font-mono font-semibold text-ivory transition-colors hover:bg-well sm:w-auto"
                    data-testid="open-primary-result"
                  >
                    <FileText size={15} className="shrink-0" />
                    Open {resolveArtifactBaseName({ ref: deliverable.primary, queueItemTitle: selected.title })}
                  </button>
                </div>
              ) : isTerminalStatus && selectedStatus === 'done' ? (
                <div className="rounded border border-softgraph bg-ink p-4 text-sm text-taupe" data-testid="primary-result-missing">
                  No business deliverable file was found for this item — see receipts and execution evidence below.
                </div>
              ) : null}

              {/* C2. Steps — the parent objective and its execution step(s), so a
                  decomposed workflow reads as one workflow with steps rather
                  than needing the Workflow/Technical accordion below to see
                  what actually ran (F-QUEUE-GROUPING). Uses the same
                  parent_id-derived pipeline the backend already computes. */}
              {pipeline?.mode === 'workflow_chain' && pipeline.nodes?.length > 1 && (
                <div className="rounded border border-softgraph bg-ink p-4" data-testid="workflow-steps-summary">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Steps</div>
                  <ul className="mt-2 space-y-1.5">
                    {pipeline.nodes.map(node => (
                      <li key={node.id} className="flex items-center gap-2 text-sm">
                        {node.status === 'done'
                          ? <CheckCircle2 size={14} className="shrink-0 text-champagne" />
                          : <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-softgraph" />}
                        {node.id === selected.id ? (
                          <span className="truncate text-stone">{node.name}</span>
                        ) : (
                          <button type="button" onClick={() => selectQueueItem(node.id)} className="truncate text-left text-stone hover:text-champagne">
                            {node.name}
                          </button>
                        )}
                        <span className="ml-auto shrink-0 font-mono text-[10px] text-taupe">{formatStatus(node.status)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* D. Other deliverables */}
              {deliverable.deliverables.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Deliverables</div>
                  <div className="mt-2 space-y-2">
                    {deliverable.deliverables.map((artifact, index) => (
                      <button
                        key={`${artifact.path}-${index}`}
                        type="button"
                        onClick={() => viewArtifact(artifact)}
                        className="flex w-full items-center justify-between gap-2 rounded border border-softgraph bg-ink px-3 py-2 text-left text-xs font-mono text-stone transition-colors hover:border-champagne"
                      >
                        <span className="min-w-0 truncate">{deliverableDisplayLabel(artifact, { queueItemTitle: selected.title })}</span>
                        <FileText size={13} className="shrink-0 text-taupe" />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* E. Required next action */}
              {selected.next_action && selectedStatus !== 'done' && (
                <div className="rounded border border-champagne/30 bg-champagne/10 p-4 text-sm" data-testid="next-action">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-champagne">What you need to do now</div>
                  <p className="mt-1.5 leading-6 text-stone">{selected.next_action}</p>
                </div>
              )}

              {selected.status === 'needs_input' && (
                <div className="rounded border border-softgraph bg-ink" data-testid="needs-input-controls">
                  <div className="border-b border-softgraph px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-taupe">Needs input</div>
                  <div className="space-y-3 px-3 py-3">
                    <div className="rounded border border-champagne/40 bg-graphite p-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-champagne">What is missing</div>
                      <div className="mt-2 text-xs leading-5 text-stone">{selected.next_action || selected.summary_for_operator || 'No specific question was recorded; inspect the context and latest receipt below.'}</div>
                      {selected.context && <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded border border-softgraph bg-ink p-2 text-xs text-stone">{selected.context}</pre>}
                    </div>
                    <FieldLabel label="Your answer">
                      <textarea
                        className={`${fieldBase} min-h-[4rem] resize-y`}
                        maxLength={2000}
                        value={answerState.answer}
                        onChange={event => updateAnswerText(event.target.value)}
                        placeholder="Answer the missing question; this is saved as a receipt and resumes the item to agent_todo"
                      />
                    </FieldLabel>
                    <button
                      type="button"
                      onClick={submitNeedsInputAnswer}
                      disabled={answerState.submitting}
                      className="inline-flex items-center gap-2 rounded bg-champagne px-3 py-2 text-xs font-mono font-semibold text-ivory transition-colors hover:bg-well disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {answerState.submitting ? 'Saving answer...' : 'Answer & resume'}
                    </button>
                    {(answerState.message || answerState.error) && (
                      <div className={`rounded border px-3 py-2 text-xs font-mono ${answerState.error ? 'border-clay/40 bg-clay/10 text-clay' : 'border-champagne/30 bg-champagne/10 text-champagne'}`}>
                        {answerState.error || answerState.message}
                      </div>
                    )}
                    <div className="text-xs font-mono text-taupe">Answer & resume attaches your answer as a local receipt and moves the item back to agent_todo through the existing status path. It does not send anything externally.</div>
                  </div>
                </div>
              )}

              {selected.external_handoff_relevant && <details className="rounded border border-champagne/30 bg-ink" data-testid="manual-handoff-details">
                <summary className="cursor-pointer select-none px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-champagne">Manual third-party handoff / dry-run only (never sent)</summary>
                <form onSubmit={submitDryRun} className="border-t border-softgraph" data-testid="manual-handoff">
                <div className="border-b border-softgraph px-3 py-2">
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
              </details>}

              {/* Progressive disclosure: everything below is execution evidence, not the outcome itself. */}
              {finalResult?.complete && (
                <details className="rounded border border-champagne/40 bg-ink" open>
                  <summary className="cursor-pointer select-none px-3 py-2 text-sm font-semibold text-ivory">Workflow complete</summary>
                  <div className="border-t border-softgraph px-3 py-2 text-xs font-mono text-taupe">
                    Parent {finalResult.parent_id || 'unknown'} / Final step {finalResult.final_item_id || 'unknown'} / Status {formatStatus(finalResult.final_item_status || finalResult.chain_status)}
                  </div>
                  <div className="flex flex-wrap gap-2 px-3 py-3">
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
                </details>
              )}

              {pipeline?.nodes?.length > 0 && (
                <details className="rounded border border-softgraph bg-ink" data-testid="pipeline-visualization" open={accordionState.workflow} onToggle={event => updateAccordion('workflow', event.target.open)}>
                  <summary className="cursor-pointer select-none px-3 py-2 text-sm font-semibold text-ivory">Workflow</summary>
                  <div className="border-t border-softgraph px-3 py-2 text-xs font-mono text-taupe">{pipeline.mode === 'workflow_chain' ? `Recorded chain ${pipeline.parent_id}` : 'Honest status-stage fallback; no step contract recorded'}</div>
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
                </details>
              )}

              <details className="rounded border border-softgraph bg-ink" data-testid="queue-detail-metadata" open={accordionState.technical} onToggle={event => updateAccordion('technical', event.target.open)}>
                <summary className="cursor-pointer select-none px-3 py-2 text-sm font-semibold text-ivory">Technical details</summary>
                <div className="border-t border-softgraph px-3 py-3">
                  <div className="mb-3 flex flex-wrap gap-2">
                    <PromptButton target="codex" busy={promptCopy.target === 'codex'} onCopy={copyPrompt} />
                    <PromptButton target="claude" busy={promptCopy.target === 'claude'} onCopy={copyPrompt} />
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <DetailRow label="ID" value={selected.id} />
                    <DetailRow label="Status" value={formatStatus(selected.status)} />
                    <DetailRow label="Running status" value={formatStatus(selected.honest_status)} />
                    <DetailRow label="Step progress" value={selected.step_progress?.label || (selected.workflow_steps?.length ? `0 of ${selected.workflow_steps.length}` : '')} />
                    <DetailRow label="Owner" value={selected.owner || 'unassigned'} />
                    <DetailRow label="Priority" value={String(selected.priority ?? 0)} />
                    <DetailRow label="Updated at" value={selected.updated_at} />
                    <DetailRow label="Created at" value={selected.created_at} />
                    <DetailRow label="Workbench" value={selected.workbench} />
                    <DetailRow label="Source" value={selected.source} />
                    <DetailRow label="Requested by" value={selected.requested_by} />
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
                </div>
              </details>

              <details className="rounded border border-softgraph bg-ink" data-testid="receipts-and-evidence" open={accordionState.receipts} onToggle={event => updateAccordion('receipts', event.target.open)}>
                <summary className="cursor-pointer select-none px-3 py-2 text-sm font-semibold text-ivory">Receipts &amp; execution evidence</summary>
                <div className="space-y-4 border-t border-softgraph px-3 py-3">
                  {(runState.running || runState.error || runState.result || showPersistedRunState) && (
                    <div className="rounded border border-softgraph bg-graphite">
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
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-taupe">Latest receipt content</div>
                    {hasReceipt ? (() => {
                      const fullText = latestReceipt?.content || latestReceipt?.summary || 'Receipt content unavailable.'
                      const isTruncated = fullText.length > 1000
                      const shownText = receiptPreviewExpanded || !isTruncated ? fullText : `${fullText.slice(0, 1000)}...`
                      return (
                        <>
                          <pre className={`${receiptPreviewExpanded ? 'max-h-[36rem]' : 'max-h-72'} overflow-auto whitespace-pre-wrap break-words rounded border border-softgraph bg-graphite px-3 py-3 text-xs leading-5 text-stone`}>
                            {shownText}
                          </pre>
                          {isTruncated && (
                            <button
                              type="button"
                              onClick={() => setReceiptPreviewExpanded(value => !value)}
                              className="mt-1 text-xs font-mono text-champagne hover:text-stone"
                            >
                              {receiptPreviewExpanded ? 'Show less' : `Show full receipt (${fullText.length.toLocaleString()} chars)`}
                            </button>
                          )}
                        </>
                      )
                    })() : (
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
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-taupe">Raw run / artifact list</div>
                    {runArtifacts.length ? (
                      <div className="space-y-2">
                        {runArtifacts.map((artifact, index) => {
                          const isOpen = activeContentTab === artifact.path
                          const isPrimaryOutput = deliverable.primary?.path === artifact.path
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
                              isOpen ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-graphite hover:border-taupe'
                            }`}
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                <div className="flex flex-wrap gap-2">
                                  {isPrimaryOutput && (
                                    <span className="rounded bg-champagne px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ivory">
                                      Primary result
                                    </span>
                                  )}
                                  {isOpen && (
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

                  <div data-testid="receipt-history-details">
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-taupe">Receipt history ({selected.receipts?.length || 0})</div>
                    {selected.receipts?.length ? (
                      <div className="space-y-2">
                        {selected.receipts.map((receipt, index) => {
                          const path = receiptLabel(receipt)
                          const isOpen = activeContentTab === path
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
                              isOpen ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-ink hover:border-taupe'
                            }`}
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div className="min-w-0">
                                {isOpen && (
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
              </details>
            </div>
          ) : (
            <div className="rounded border border-softgraph bg-ink px-4 py-10 text-center text-xs font-mono text-taupe">
              {items.length ? 'Select an item to inspect details.' : 'Queue details will appear when local items exist.'}
            </div>
          )}
        </div>
        )}
        </div>
      </section>
      </div>
      )}
      </div>

      {deletionState.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="presentation" data-testid="task-deletion-overlay">
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-deletion-title"
            onSubmit={submitTaskDeletion}
            className="w-full max-w-xl rounded-lg border border-clay/50 bg-graphite p-5 shadow-2xl"
            data-testid="task-deletion-dialog"
          >
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="mt-0.5 flex-shrink-0 text-clay" />
              <div>
                <h2 id="task-deletion-title" className="text-lg font-semibold text-ivory">Permanently delete this task?</h2>
                <p className="mt-1 text-sm text-taupe">This removes the live queue record. Existing receipts and artifacts are not deleted.</p>
              </div>
            </div>
            <div className="mt-4 rounded border border-softgraph bg-ink p-3">
              <div className="font-mono text-xs text-champagne" data-testid="task-deletion-item-id">{deletionState.itemId}</div>
              <div className="mt-1 break-words text-sm text-stone" data-testid="task-deletion-item-title">{deletionState.title}</div>
            </div>
            <div className="mt-4 space-y-3">
              <FieldLabel label="Short deletion reason">
                <input
                  className={fieldBase}
                  value={deletionState.reason}
                  maxLength={240}
                  onChange={event => setDeletionState(current => ({ ...current, reason: event.target.value }))}
                  placeholder="Why this task should be permanently removed"
                  autoFocus
                  data-testid="task-deletion-reason"
                />
              </FieldLabel>
              <FieldLabel label={`Type ${deletionState.itemId} to confirm`}>
                <input
                  className={fieldBase}
                  value={deletionState.confirmation}
                  onChange={event => setDeletionState(current => ({ ...current, confirmation: event.target.value }))}
                  autoComplete="off"
                  data-testid="task-deletion-confirmation"
                />
              </FieldLabel>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={cancelTaskDeletion}
                disabled={deletionState.submitting}
                className="rounded border border-softgraph bg-ink px-3 py-2 text-xs font-mono text-stone disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!canSubmitTaskDeletion({ itemId: deletionState.itemId, reason: deletionState.reason, confirmation: deletionState.confirmation, submitting: deletionState.submitting })}
                className="inline-flex items-center gap-2 rounded bg-clay px-3 py-2 text-xs font-mono font-semibold text-ivory transition-colors hover:bg-clay/80 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="confirm-task-deletion"
              >
                <Trash2 size={13} />{deletionState.submitting ? 'Deleting permanently...' : 'Permanently delete'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
