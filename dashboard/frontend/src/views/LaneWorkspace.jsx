import { useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { attachQueueReceipt, closeQueueItemReview, getQueueItemsForScope, runQueueItem, updateQueueItemStatus } from '../api'
import { ActionButton, EmptyState, PageHeader, QueueWorkItemCard } from '../components/DashboardKit'
import { HumanReviewCard } from '../components/HumanReviewCard'
import { isLaneSelectable, performReadyAction, performReviewAction, performSelectedAction, REVIEW_ACTIONS, reviewActionNeedsNote, selectedLaneItems, unblockLaneItem } from '../laneWorkspaceActions'
import { buildLaneWorkspace, LANE_FILTERS, normalizeLane } from '../laneWorkspaceState'

const laneTitle = lane => lane === 'unassigned'
  ? 'Unassigned Lane'
  : `${lane.charAt(0).toUpperCase()}${lane.slice(1)} Lane`

const actionError = error => error?.response?.data?.detail || error?.message || 'Queue action failed'

function ReviewActionCard({ item, busy, feedback, onAction, onReviewSaved }) {
  const [note, setNote] = useState('')
  const runAction = action => {
    if (reviewActionNeedsNote(item, action) && !note.trim()) return
    const label = REVIEW_ACTIONS.find(candidate => candidate.id === action)?.label || action
    if (!globalThis.confirm?.(`${label} ${item.id}? This changes the queue item state.`)) return
    onAction(item, action, note)
  }
  if (item.status === 'human_review') {
    return <HumanReviewCard item={item} onSaved={onReviewSaved} />
  }
  return (
    <div className="overflow-hidden rounded-lg border border-champagne/60 bg-graphite" data-lane-action-card-id={item.id}>
      <QueueWorkItemCard item={item} />
      <div className="space-y-2 border-t border-softgraph p-3">
        <textarea
          aria-label={`Operator note for ${item.id}`}
          className="min-h-16 w-full resize-y rounded border border-softgraph bg-ink px-3 py-2 text-xs text-stone outline-none placeholder:text-taupe focus:border-champagne"
          maxLength={500}
          value={note}
          onChange={event => setNote(event.target.value)}
          placeholder={item.status === 'needs_input' ? 'Answer or operator note (required)' : 'Operator note (required for changes or reject)'}
        />
        <div className="flex flex-wrap gap-2">
          {REVIEW_ACTIONS.map(action => (
            <ActionButton
              key={action.id}
              kind={action.id === 'approve' ? 'primary' : action.id === 'reject' ? 'locked' : 'neutral'}
              onClick={() => runAction(action.id)}
              disabled={busy || (reviewActionNeedsNote(item, action.id) && !note.trim())}
              data-lane-action={action.id}
            >
              {action.label}
            </ActionButton>
          ))}
        </div>
        {feedback && <p className={`text-xs font-mono ${feedback.kind === 'error' ? 'text-clay' : 'text-champagne'}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p>}
      </div>
    </div>
  )
}

function ReadyActionCard({ item, selected, busy, feedback, onSelectionChange, onAction }) {
  return (
    <div className="rounded border border-softgraph bg-graphite/40 p-2" data-lane-action-card-id={item.id}>
      <label className="mb-2 inline-flex items-center gap-2 px-1 text-xs font-semibold text-stone">
        <input type="checkbox" checked={selected} disabled={busy} onChange={event => onSelectionChange(item.id, event.target.checked)} aria-label={`Select ${item.id}`} />
        Select
      </label>
      <QueueWorkItemCard item={item} />
      <div className="mt-2 flex flex-wrap gap-2 px-1">
        <ActionButton kind="primary" onClick={() => onAction(item, 'run')} disabled={busy} data-lane-action="run">Run now</ActionButton>
        <ActionButton kind="locked" onClick={() => onAction(item, 'cancel')} disabled={busy} data-lane-action="cancel">Cancel</ActionButton>
      </div>
      {feedback && <p className={`mt-2 px-1 text-xs font-mono ${feedback.kind === 'error' ? 'text-clay' : 'text-champagne'}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p>}
    </div>
  )
}

function BlockedActionCard({ item, busy, feedback, onUnblock }) {
  return (
    <div className="rounded border border-clay/50 bg-graphite/40 p-2" data-lane-action-card-id={item.id}>
      <QueueWorkItemCard item={{ ...item, blocked_reason: null, reason: null }} />
      <p className="mt-2 px-1 text-xs text-clay" data-blocked-reason={item.id}>{item.blocked_reason || item.reason || 'No blocked reason was provided.'}</p>
      <div className="mt-2 px-1"><ActionButton onClick={() => onUnblock(item)} disabled={busy} data-lane-action="unblock">Unblock</ActionButton></div>
      {feedback && <p className={`mt-2 px-1 text-xs font-mono ${feedback.kind === 'error' ? 'text-clay' : 'text-champagne'}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p>}
    </div>
  )
}

export function LaneWorkspaceContent({ workspace, loading, error, selectedIds = [], busyIds = [], feedback = {}, bulkState = {}, onFilterChange, onRefresh, onReviewSaved, onSelectionChange = () => {}, onSelectAll = () => {}, onItemAction = () => {}, onUnblock = () => {}, onBulkAction = () => {} }) {
  const activeLabel = LANE_FILTERS.find(filter => filter.id === workspace.activeFilter)?.label || 'All Active'
  const selectableItems = workspace.items.filter(isLaneSelectable)
  const selectedItems = selectedLaneItems(workspace.items, selectedIds)
  const allSelected = selectableItems.length > 0 && selectedItems.length === selectableItems.length
  const busy = new Set(busyIds)
  return (
    <section data-lane-workspace={workspace.lane}>
      <PageHeader
        title={laneTitle(workspace.lane || 'unassigned')}
        question={`${workspace.total} lane-scoped queue item${workspace.total === 1 ? '' : 's'} · ${activeLabel}`}
        actions={<ActionButton onClick={onRefresh} disabled={loading}><RefreshCw size={13} />{loading ? 'Refreshing' : 'Refresh'}</ActionButton>}
      />

      <div className="mb-5 grid grid-cols-2 gap-2 lg:grid-cols-6" aria-label="Lane queue filters">
        {LANE_FILTERS.map(filter => {
          const active = workspace.activeFilter === filter.id
          return (
            <button
              type="button"
              key={filter.id}
              onClick={() => onFilterChange(filter.id)}
              aria-pressed={active}
              data-lane-filter={filter.id}
              className={`rounded border px-3 py-3 text-left transition-colors ${active ? 'border-champagne/60 bg-champagne/10' : 'border-softgraph bg-graphite/70 hover:border-champagne/40'}`}
            >
              <div className={`text-[10px] font-mono uppercase ${active ? 'text-champagne' : 'text-taupe'}`}>{filter.label}</div>
              <div className={`mt-1 font-mono text-xl ${active ? 'text-champagne' : 'text-ivory'}`} data-lane-filter-count={filter.id}>{workspace.counts[filter.id] || 0}</div>
            </button>
          )
        })}
      </div>

      {error && <div className="mb-4 rounded border border-clay/60 bg-clay/10 px-4 py-3 text-sm text-clay">{error.message || 'Queue unavailable'}</div>}
      {selectableItems.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-softgraph bg-graphite/70 p-3" data-lane-selection={workspace.activeFilter}>
          <label className="mr-auto inline-flex items-center gap-2 text-xs font-semibold text-stone">
            <input type="checkbox" checked={allSelected} onChange={event => onSelectAll(event.target.checked, selectableItems)} aria-label="Select all current-filter ready items" />
            {selectedItems.length} selected in current filter
          </label>
          <ActionButton kind="primary" disabled={!selectedItems.length || bulkState.busy} onClick={() => onBulkAction('run')} data-lane-bulk-action="run">Run selected</ActionButton>
          <ActionButton kind="locked" disabled={!selectedItems.length || bulkState.busy} onClick={() => onBulkAction('cancel')} data-lane-bulk-action="cancel">Cancel selected</ActionButton>
          {bulkState.message && <span className={`w-full text-xs font-mono ${bulkState.kind === 'error' ? 'text-clay' : 'text-champagne'}`} role={bulkState.kind === 'error' ? 'alert' : 'status'}>{bulkState.message}</span>}
        </div>
      )}
      {loading && workspace.total === 0 ? (
        <EmptyState title="Loading lane queue" detail="Reading the local queue workspace." />
      ) : workspace.items.length ? (
        <div className="space-y-2" data-lane-results={workspace.activeFilter}>
          {workspace.items.map(item => ['human_review', 'needs_input'].includes(item.status)
            ? <ReviewActionCard key={item.id} item={item} busy={busy.has(item.id)} feedback={feedback[item.id]} onAction={onItemAction} onReviewSaved={onReviewSaved} />
            : isLaneSelectable(item)
              ? <ReadyActionCard key={item.id} item={item} selected={selectedIds.includes(item.id)} busy={busy.has(item.id)} feedback={feedback[item.id]} onSelectionChange={onSelectionChange} onAction={onItemAction} />
              : item.status === 'blocked'
                ? <BlockedActionCard key={item.id} item={item} busy={busy.has(item.id)} feedback={feedback[item.id]} onUnblock={onUnblock} />
                : <QueueWorkItemCard key={item.id} item={item} lane={workspace.lane} />)}
        </div>
      ) : (
        <EmptyState title={`No ${activeLabel} items`} detail={`There are no ${activeLabel.toLowerCase()} items in this lane.`} />
      )}
    </section>
  )
}

export default function LaneWorkspace({ initialFilters = {}, refresh }) {
  const lane = normalizeLane(initialFilters.lane) || 'unassigned'
  const [items, setItems] = useState([])
  const [selectedFilter, setSelectedFilter] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [busyIds, setBusyIds] = useState([])
  const [feedback, setFeedback] = useState({})
  const [bulkState, setBulkState] = useState({ busy: false, kind: '', message: '' })
  const [state, setState] = useState({ loading: true, error: null })

  const endpoints = useMemo(() => ({
    attachReceipt: attachQueueReceipt,
    closeReview: closeQueueItemReview,
    runItem: runQueueItem,
  }), [])

  const loadItems = async () => {
    setState(current => ({ ...current, loading: true }))
    try {
      const data = await getQueueItemsForScope('all')
      if (data?.success === false) throw new Error(data.reason || 'Queue unavailable')
      setItems(Array.isArray(data?.items) ? data.items : [])
      setState({ loading: false, error: null })
    } catch (error) {
      setState({ loading: false, error })
    }
  }

  useEffect(() => {
    setSelectedFilter(null)
    setSelectedIds([])
    loadItems()
  }, [lane])

  const workspace = useMemo(
    () => buildLaneWorkspace(items, lane, selectedFilter),
    [items, lane, selectedFilter],
  )

  useEffect(() => {
    setSelectedIds(current => {
      const next = selectedLaneItems(workspace.items, current).map(item => item.id)
      return next.length === current.length && next.every((id, index) => id === current[index]) ? current : next
    })
  }, [workspace.items])

  const changeFilter = filter => {
    setSelectedIds([])
    setBulkState({ busy: false, kind: '', message: '' })
    setSelectedFilter(filter)
  }

  const changeSelection = (id, checked) => {
    setSelectedIds(current => checked ? [...new Set([...current, id])] : current.filter(value => value !== id))
  }

  const selectAll = (checked, selectableItems) => {
    setSelectedIds(checked ? selectableItems.map(item => item.id) : [])
  }

  const finishMutation = async () => {
    await loadItems()
    refresh?.()
  }

  const itemAction = async (item, action, note = '') => {
    setBusyIds(current => [...new Set([...current, item.id])])
    setFeedback(current => ({ ...current, [item.id]: { kind: '', text: '' } }))
    try {
      if (['human_review', 'needs_input'].includes(item.status)) await performReviewAction(item, action, note, endpoints)
      else await performReadyAction(item, action, endpoints)
      setFeedback(current => ({ ...current, [item.id]: { kind: 'success', text: 'Action saved.' } }))
      setSelectedIds(current => current.filter(id => id !== item.id))
      await finishMutation()
    } catch (error) {
      setFeedback(current => ({ ...current, [item.id]: { kind: 'error', text: actionError(error) } }))
    } finally {
      setBusyIds(current => current.filter(id => id !== item.id))
    }
  }

  const unblock = async item => {
    setBusyIds(current => [...new Set([...current, item.id])])
    try {
      await unblockLaneItem(item, updateQueueItemStatus)
      setFeedback(current => ({ ...current, [item.id]: { kind: 'success', text: 'Moved to agent_todo.' } }))
      await finishMutation()
    } catch (error) {
      setFeedback(current => ({ ...current, [item.id]: { kind: 'error', text: actionError(error) } }))
    } finally {
      setBusyIds(current => current.filter(id => id !== item.id))
    }
  }

  const bulkAction = async action => {
    const targets = selectedLaneItems(workspace.items, selectedIds)
    if (!targets.length || bulkState.busy) return
    setBulkState({ busy: true, kind: '', message: `${action === 'run' ? 'Running' : 'Cancelling'} ${targets.length} item${targets.length === 1 ? '' : 's'} sequentially…` })
    setBusyIds(targets.map(item => item.id))
    const results = await performSelectedAction(targets, action, endpoints)
    const failures = results.filter(result => !result.success)
    setSelectedIds(failures.map(result => result.id))
    setBusyIds([])
    setBulkState({
      busy: false,
      kind: failures.length ? 'error' : 'success',
      message: failures.length ? `${results.length - failures.length} succeeded; ${failures.length} failed.` : `${results.length} item${results.length === 1 ? '' : 's'} ${action === 'run' ? 'ran' : 'cancelled'} sequentially.`,
    })
    await finishMutation()
  }

  const reviewSaved = () => {
    loadItems()
    refresh?.()
  }

  return (
    <LaneWorkspaceContent
      workspace={workspace}
      loading={state.loading}
      error={state.error}
      selectedIds={selectedIds}
      busyIds={busyIds}
      feedback={feedback}
      bulkState={bulkState}
      onFilterChange={changeFilter}
      onRefresh={loadItems}
      onReviewSaved={reviewSaved}
      onSelectionChange={changeSelection}
      onSelectAll={selectAll}
      onItemAction={itemAction}
      onUnblock={unblock}
      onBulkAction={bulkAction}
    />
  )
}
