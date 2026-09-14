import { artifactTabLabel, detectNoExternalAction, extractRepeatedEntitySummary, parseMarkdownBlocks } from './artifactPreview.js'

export const HUMAN_NEEDED_STATUSES = new Set(['human_review', 'needs_input', 'blocked'])

export const normalizedStatus = value => String(value || '').trim().toLowerCase()

export const humanNeededItems = items => (Array.isArray(items) ? items : [])
  .filter(item => HUMAN_NEEDED_STATUSES.has(normalizedStatus(item?.status)) || (Array.isArray(item?.needs_me) && item.needs_me.length > 0))

export function normalizeCockpitQueue(cockpit) {
  if (!cockpit || cockpit.error) return cockpit
  const source = Array.isArray(cockpit.queue_items) ? cockpit.queue_items : cockpit.needs_me
  const needsMe = humanNeededItems(source)
  return {
    ...cockpit,
    needs_me: needsMe,
    needs_me_count: needsMe.length,
    human_needed_count: needsMe.length,
  }
}

export function mergeQueueSummary(cockpit, summary) {
  if (!summary || summary.success === false) return preserveQueueDataOnRefreshFailure(cockpit)
  const needsMe = humanNeededItems(summary.needsMeItems)
  return {
    ...(cockpit && !cockpit.error ? cockpit : {}),
    counts: summary.counts || cockpit?.counts || {},
    needs_me: needsMe,
    needs_me_count: needsMe.length,
    human_needed_count: needsMe.length,
    queueSummaryLoaded: true,
    refreshError: false,
  }
}

export function preserveQueueDataOnRefreshFailure(current) {
  if (!current) return { error: true, refreshError: true }
  return { ...current, refreshError: true }
}

// A background list refresh always returns compact rows (detail_loaded: false).
// Overwriting an already-loaded rich row with that compact row makes every
// detail-dependent section (pipeline, artifacts, receipts, final result) vanish
// and then reappear a moment later once the on-demand detail refetch resolves —
// that flicker is what made the page appear to jump while an operator was
// reading a long selected item. Keep the previously loaded rich row whenever the
// backend's content fingerprint (record_hash) says nothing actually changed.
export function mergeRefreshedQueueItems(currentItems, freshItems) {
  const current = Array.isArray(currentItems) ? currentItems : []
  const fresh = Array.isArray(freshItems) ? freshItems : []
  const byId = new Map(current.map(item => [item.id, item]))
  return fresh.map(freshItem => {
    const existing = byId.get(freshItem.id)
    if (existing?.detail_loaded && existing.record_hash && existing.record_hash === freshItem.record_hash) {
      return { ...existing, ...freshItem, detail_loaded: true }
    }
    return freshItem
  })
}

export function resolveQueueSelection({ items, currentId, preferredId, nextId, selectionChanged = false }) {
  const list = Array.isArray(items) ? items : []
  const exists = id => Boolean(id) && list.some(item => item.id === id)
  if (selectionChanged && exists(currentId)) return currentId
  if (exists(preferredId)) return preferredId
  if (exists(currentId)) return currentId
  if (exists(nextId)) return nextId
  return list[0]?.id || null
}

// Deterministic artifact classification (F-DELIVERABLE-CLASSIFICATION). Three
// classes, in Primary Result preference order:
//   business_result      — a generated report/review package/final output.
//   execution_evidence    — queue/receipts, logs, or anything else that only
//                           records that a run happened rather than what it
//                           produced.
//   workflow_supporting   — the workflow/skill *definitions* a run followed
//                           (always literally named workflow.md / SKILL.md by
//                           repo convention), not a definition it produced.
// This is path/filename-shape driven only — it never matches a specific
// item's filename — so it generalizes across every workflow, not just the
// Internal Outreach Daily example that exposed the bug.
export const ARTIFACT_CLASS_RANK = { business_result: 0, execution_evidence: 1, workflow_supporting: 2 }

export function classifyArtifact(ref) {
  const path = String(ref?.path || ref || '').replace(/\\/g, '/').trim()
  const name = path.split('/').pop() || ''
  if (/^queue\/receipts\//i.test(path) || /^logs\//i.test(path) || /ledger/i.test(name)) return 'execution_evidence'
  if (/^workflow\.md$/i.test(name) || /^skill\.md$/i.test(name)) return 'workflow_supporting'
  return 'business_result'
}

// Picks the single best available business deliverable for a work item out of
// everything already surfaced by the backend (a completed workflow's final
// artifact, the detail endpoint's primary_artifact, or the run's artifact
// list) instead of leaving the operator to infer it from a receipt path or —
// worse — land on a workflow definition file because it happened to be
// mentioned earliest in a receipt's prose. A real business result always
// outranks workflow-definition and execution-evidence candidates; ties keep
// the original discovery order (finalArtifact/primaryArtifact first). Any
// other available business-result or execution-evidence artifact becomes a
// secondary "Deliverable"; workflow-supporting files stay out of that list
// (they remain visible in Technical details / the raw artifact list).
export function resolvePrimaryDeliverable({ finalArtifact, primaryArtifact, runArtifacts, latestReceiptPath } = {}) {
  const candidates = []
  if (finalArtifact?.available !== false && finalArtifact?.path) candidates.push(finalArtifact)
  if (primaryArtifact?.available !== false && primaryArtifact?.path) candidates.push(primaryArtifact)
  for (const artifact of Array.isArray(runArtifacts) ? runArtifacts : []) {
    if (artifact?.available && artifact.path && artifact.path !== latestReceiptPath) candidates.push(artifact)
  }
  const seen = new Set()
  const unique = candidates.filter(candidate => {
    if (seen.has(candidate.path)) return false
    seen.add(candidate.path)
    return true
  })
  const ranked = [...unique].sort((a, b) => ARTIFACT_CLASS_RANK[classifyArtifact(a)] - ARTIFACT_CLASS_RANK[classifyArtifact(b)])
  const [primary = null, ...rest] = ranked
  const deliverables = rest.filter(candidate => classifyArtifact(candidate) !== 'workflow_supporting')
  return { primary, deliverables }
}

const ID_SHAPED_RE = /^[A-Z]{2,8}[-\s]?\d{2,4}[-\s]?\d*/

// Human title-resolution priority (F-ARTIFACT-TITLE): a semantic role label,
// then the work item's own title, then the artifact's own document heading,
// then a cleaned filename, and only an AOS/queue ID as the last resort. An
// AOS-ID-shaped cleaned filename is treated as "no real name" so the queue
// item title (or heading) wins instead.
export function resolveArtifactBaseName({ ref, queueItemTitle, headingText } = {}) {
  const semanticLabel = String(ref?.semanticLabel || '').trim()
  if (semanticLabel) return semanticLabel
  const cleanedName = artifactTabLabel(ref)
  const looksLikeId = ID_SHAPED_RE.test(cleanedName)
  const title = String(queueItemTitle || '').trim()
  if (title && (looksLikeId || !cleanedName)) return title
  const heading = String(headingText || '').trim()
  if (heading && looksLikeId) return heading
  return cleanedName || title || heading || 'Artifact'
}

// Generic role word derived from classification and generic outcome/summary
// keywords in the path — never from one workflow's specific filename.
export function artifactRoleWord(ref, classification) {
  const cls = classification || classifyArtifact(ref)
  if (cls === 'execution_evidence') return 'Evidence'
  if (cls === 'workflow_supporting') return 'Reference'
  const name = String(ref?.path || ref?.name || '').toLowerCase()
  if (/outcome|summary|synthesis/.test(name)) return 'Summary'
  return 'Report'
}

export function resolveArtifactTabTitle({ ref, queueItemTitle, headingText, classification } = {}) {
  const base = resolveArtifactBaseName({ ref, queueItemTitle, headingText })
  const role = artifactRoleWord(ref, classification)
  return `${base} — ${role}`
}

export function deliverableDisplayLabel(ref, { queueItemTitle, headingText, isPrimary = false } = {}) {
  const title = resolveArtifactTabTitle({ ref, queueItemTitle, headingText })
  return isPrimary ? `★ ${title}` : title
}

// --- Session-scoped Work Queue UI state --------------------------------
// Open artifact tabs and per-item accordion state must survive navigating
// away to another dashboard page and back (and, where practical, a hard
// reload), the same way askDavidState.js persists the Ask David thread. Only
// enough identity to reopen an artifact is kept — never its content.
export const QUEUE_TABS_STORAGE_KEY = 'aos.dashboard.queue.tabs.v1'
export const QUEUE_ACCORDION_STORAGE_KEY = 'aos.dashboard.queue.accordion.v1'
export const DEFAULT_ACCORDION_STATE = { workflow: false, technical: false, receipts: false }

export function loadPersistedArtifactTabs(storage) {
  try {
    const raw = storage?.getItem(QUEUE_TABS_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    const tabs = Array.isArray(parsed?.tabs)
      ? parsed.tabs.filter(tab => tab && typeof tab.id === 'string' && typeof tab.path === 'string')
      : []
    const activeContentTab = typeof parsed?.activeContentTab === 'string' ? parsed.activeContentTab : 'overview'
    return { tabs, activeContentTab }
  } catch {
    return { tabs: [], activeContentTab: 'overview' }
  }
}

export function persistArtifactTabs(storage, tabs, activeContentTab) {
  try {
    const safeTabs = (Array.isArray(tabs) ? tabs : []).map(tab => ({
      id: tab.id,
      path: tab.path,
      label: tab.label,
      category: tab.category,
      extension: tab.extension,
    }))
    storage?.setItem(QUEUE_TABS_STORAGE_KEY, JSON.stringify({ tabs: safeTabs, activeContentTab: activeContentTab || 'overview' }))
  } catch {
    // sessionStorage unavailable or full; open tabs simply won't persist.
  }
}

export function loadAccordionState(storage, itemId) {
  try {
    const raw = storage?.getItem(QUEUE_ACCORDION_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    const forItem = itemId && parsed && typeof parsed === 'object' ? parsed[itemId] : null
    return { ...DEFAULT_ACCORDION_STATE, ...(forItem && typeof forItem === 'object' ? forItem : {}) }
  } catch {
    return { ...DEFAULT_ACCORDION_STATE }
  }
}

export function persistAccordionState(storage, itemId, state) {
  if (!itemId) return
  try {
    const raw = storage?.getItem(QUEUE_ACCORDION_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    const next = { ...(parsed && typeof parsed === 'object' ? parsed : {}), [itemId]: state }
    storage?.setItem(QUEUE_ACCORDION_STORAGE_KEY, JSON.stringify(next))
  } catch {
    // sessionStorage unavailable or full; accordion state simply won't persist.
  }
}

// --- Parent objective / child step grouping (F-QUEUE-GROUPING) -------------
// The backend already treats `parent_id` as the authoritative parent/child
// link for a decomposed workflow (see the pipeline and final-result lookups
// in dashboard/backend/main.py, which walk the same field). An operator who
// asked for one workflow to run should see one top-level queue entry, not the
// parent objective and its execution child rendered as two equivalent peer
// jobs. This folds any item whose parent_id resolves to another item in the
// same list into that parent's childSteps, ordered by step_index; anything
// without a resolvable parent (including older multi-step chains that never
// set parent_id) is returned untouched. Purely a display-layer transform — it
// never mutates the underlying record or execution state.
export function groupWorkflowChildren(items) {
  const list = Array.isArray(items) ? items : []
  const byId = new Map(list.map(item => [item.id, item]))
  const childrenByParent = new Map()
  list.forEach(item => {
    const parentId = item?.parent_id
    if (!parentId || parentId === item.id || !byId.has(parentId)) return
    const bucket = childrenByParent.get(parentId) || []
    bucket.push(item)
    childrenByParent.set(parentId, bucket)
  })
  return list
    .filter(item => !(item?.parent_id && childrenByParent.has(item.parent_id)))
    .map(item => {
      const children = childrenByParent.get(item.id)
      if (!children) return item
      const childSteps = [...children].sort((a, b) => (a.step_index ?? 0) - (b.step_index ?? 0))
      return { ...item, childSteps }
    })
}

// A grouped card should still match a status/owner/lane/source filter that
// only the folded-away child (not the parent) satisfies — otherwise grouping
// would silently hide real matching work from an existing filter chip. The
// caller's own per-row predicate is reused so this stays agnostic of what a
// "match" means.
export const groupEntryMatches = (item, predicate) =>
  predicate(item) || (Array.isArray(item.childSteps) && item.childSteps.some(child => predicate(child)))

// Deterministic, no-fetch business-outcome line for a terminal queue card
// (F-LIST-OUTCOME). Only reads data the frontend already holds in memory:
// either a previously opened item's cached primary_artifact content (never
// fetched here — fetching per row would reintroduce the list-refresh cost the
// compact-row design in dashboard/backend/main.py exists to avoid), or the
// compact row's own backend-computed summary_for_operator. Never invents a
// number or outcome that is not already present in loaded data.
export function richListOutcomeLine(item) {
  // A grouped parent's own record is usually just the orchestration wrapper
  // (its receipt literally says "Executive result" — see
  // _queue_receipt_prose_summary in dashboard/backend/main.py); the actual
  // business content lives on whichever folded child step produced it, so a
  // grouped card's outcome line checks the parent first, then its steps.
  const candidates = [item, ...(Array.isArray(item?.childSteps) ? item.childSteps : [])]
  for (const candidate of candidates) {
    const primary = candidate?.primary_artifact
    if (primary?.content && /\.md$/i.test(primary.path || '')) {
      const blocks = parseMarkdownBlocks(primary.content)
      const highlights = extractRepeatedEntitySummary(blocks)
      if (highlights) {
        const topic = highlights.heading.replace(/^selected\s+/i, '').trim() || 'items'
        const noExternalAction = detectNoExternalAction(primary.content)
        return `${highlights.count} ${topic} selected${noExternalAction ? ' · No-send review ready' : ''}`
      }
    }
  }
  return String(item?.summary_for_operator || '').trim()
}

// --- Requested-delivery evidence (F-DELIVERY-EVIDENCE) ---------------------
// Generic, deterministic detection of "deliver this result somewhere"
// language (e.g. "send me a Telegram message with the file attached") in an
// item's own recorded request text, and whether the item's own receipts/
// summary contain matching completion evidence for that channel. Never
// fabricates a status: an item with no such request text yields null, and
// completion is only ever true when the evidence text itself says so.
const DELIVERY_CHANNEL_RE = /\b(telegram|slack|email|whatsapp|sms)\b/i
const DELIVERY_VERB_RE = /\b(send|sent|message|attach|attached|deliver|delivered|dm)\b/i

export function detectRequestedDeliveryChannel(text) {
  const value = String(text || '')
  const lines = value.split(/\n+/)
  for (const line of lines) {
    if (DELIVERY_CHANNEL_RE.test(line) && DELIVERY_VERB_RE.test(line)) {
      const match = line.match(DELIVERY_CHANNEL_RE)
      if (match) return match[1].toLowerCase()
    }
  }
  return null
}

export function resolveRequestedDeliveryStatus(item) {
  const requestText = [
    item?.context,
    item?.objective?.david_handoff?.operator_message,
    item?.objective?.david_handoff?.handed_objective,
    item?.objective?.original_command,
  ].filter(Boolean).join('\n')
  const channel = detectRequestedDeliveryChannel(requestText)
  if (!channel) return null
  const evidenceText = [
    item?.summary_for_operator,
    item?.latest_receipt?.content,
    item?.latest_receipt?.summary,
  ].filter(Boolean).join('\n')
  const completionRe = new RegExp(`\\b${channel}\\b[^.\\n]{0,80}\\b(sent|delivered|transmitted)\\b|\\b(sent|delivered|transmitted)\\b[^.\\n]{0,80}\\b${channel}\\b`, 'i')
  return { channel, completed: completionRe.test(evidenceText) }
}

export function selectionAfterTaskDeletion(items, deletedId) {
  const list = Array.isArray(items) ? items : []
  const deletedIndex = list.findIndex(item => item?.id === deletedId)
  const remaining = list.filter(item => item?.id !== deletedId)
  if (!remaining.length) return { items: remaining, selectedId: null }
  const nextIndex = deletedIndex < 0 ? 0 : Math.min(deletedIndex, remaining.length - 1)
  return { items: remaining, selectedId: remaining[nextIndex]?.id || null }
}

export const canSubmitTaskDeletion = ({ itemId, reason, confirmation, submitting }) =>
  !submitting && Boolean(itemId) && String(reason || '').trim().length > 0 && String(reason || '').trim().length <= 240 && confirmation === itemId

export function taskDeletionFailureMessage(detail) {
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (!detail || typeof detail !== 'object') return 'Task deletion failed without a usable backend reason.'
  const message = String(detail.message || detail.code || 'Task deletion was refused.').trim()
  const dependentIds = Array.isArray(detail.blockers?.dependent_ids) ? detail.blockers.dependent_ids.filter(Boolean) : []
  return dependentIds.length ? `${message} Blocking dependents: ${dependentIds.join(', ')}.` : message
}
