import test from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyArtifact,
  DEFAULT_ACCORDION_STATE,
  deliverableDisplayLabel,
  detectRequestedDeliveryChannel,
  groupEntryMatches,
  groupWorkflowChildren,
  humanNeededItems,
  loadAccordionState,
  loadPersistedArtifactTabs,
  mergeQueueSummary,
  mergeRefreshedQueueItems,
  normalizeCockpitQueue,
  persistAccordionState,
  persistArtifactTabs,
  preserveQueueDataOnRefreshFailure,
  resolveArtifactBaseName,
  resolveArtifactTabTitle,
  resolvePrimaryDeliverable,
  resolveQueueSelection,
  resolveRequestedDeliveryStatus,
  richListOutcomeLine,
} from '../src/queueState.js'

function fakeStorage(initial = {}) {
  const data = { ...initial }
  return {
    getItem: key => (key in data ? data[key] : null),
    setItem: (key, value) => { data[key] = value },
    removeItem: key => { delete data[key] },
    _data: data,
  }
}

const fixture = [
  { id: 'AOS-2026-0078', status: 'human_review', owner: 'codex', workbench: 'codex' },
  { id: 'AOS-2026-0063', status: 'needs_input', owner: 'operations' },
  { id: 'AOS-2026-0020', status: 'blocked', owner: 'operations' },
  { id: 'AOS-2026-0079', status: 'inbox' },
  { id: 'AOS-2026-0077', status: 'done' },
  { id: 'AOS-2026-0001', status: 'cancelled' },
]

test('Needs Me includes review, input, and blocked real-shaped items only', () => {
  const result = humanNeededItems(fixture)
  assert.deepEqual(result.map(item => item.id), ['AOS-2026-0078', 'AOS-2026-0063', 'AOS-2026-0020'])
  assert.equal(result.find(item => item.id === 'AOS-2026-0078').status, 'human_review')
})

test('Needs Me includes metadata alerts without changing the queue status', () => {
  const result = humanNeededItems([
    { id: 'A', status: 'done', needs_me: ['excessive model turns'] },
    { id: 'B', status: 'agent_todo', needs_me: ['consider decomposing'] },
    { id: 'C', status: 'done', needs_me: [] },
  ])
  assert.deepEqual(result.map(item => item.id), ['A', 'B'])
})

test('Needs Me count equals the full rendered qualifying item set', () => {
  const queue_items = Array.from({ length: 9 }, (_, index) => ({
    id: `AOS-2026-${70 + index}`,
    status: ['human_review', 'needs_input', 'blocked'][index % 3],
  }))
  const cockpit = normalizeCockpitQueue({ queue_items, needs_me: [], needs_me_count: 0 })
  assert.equal(cockpit.needs_me_count, 9)
  assert.equal(cockpit.needs_me.length, cockpit.needs_me_count)
})

test('refresh normalization preserves the same qualifying IDs', () => {
  const first = normalizeCockpitQueue({ queue_items: fixture })
  const refreshed = normalizeCockpitQueue({ queue_items: fixture.map(item => ({ ...item })) })
  assert.deepEqual(refreshed.needs_me.map(item => item.id), first.needs_me.map(item => item.id))
})

test('lightweight queue summary repairs an unavailable Cockpit rail', () => {
  const result = mergeQueueSummary({ error: true }, {
    success: true,
    counts: { human_review: 1, needs_input: 1, blocked: 1 },
    needsMeItems: fixture,
  })
  assert.equal(result.queueSummaryLoaded, true)
  assert.equal(result.needs_me_count, 3)
  assert.deepEqual(result.needs_me.map(item => item.id), ['AOS-2026-0078', 'AOS-2026-0063', 'AOS-2026-0020'])
})

test('failed or timed-out refresh preserves prior queue data and counts', () => {
  const prior = {
    counts: { human_review: 2, needs_input: 1, blocked: 1, done: 7 },
    needs_me: fixture.slice(0, 3),
    needs_me_count: 3,
    queue_items: fixture,
  }
  const failedSummary = mergeQueueSummary(prior, { success: false, counts: { human_review: 0 }, needsMeItems: [] })
  assert.equal(failedSummary.refreshError, true)
  assert.deepEqual(failedSummary.counts, prior.counts)
  assert.equal(failedSummary.needs_me_count, 3)

  const timedOut = preserveQueueDataOnRefreshFailure(prior)
  assert.equal(timedOut.refreshError, true)
  assert.deepEqual(timedOut.queue_items, fixture)
})

test('a late refresh for item A cannot overwrite a newer item B selection', () => {
  const items = [{ id: 'A' }, { id: 'B' }]
  assert.equal(resolveQueueSelection({ items, currentId: 'B', preferredId: 'A', selectionChanged: true }), 'B')
  assert.equal(resolveQueueSelection({ items, currentId: 'A', preferredId: 'B', selectionChanged: false }), 'B')
})

test('selection safely re-resolves when the selected item disappears', () => {
  const items = [{ id: 'B' }, { id: 'C' }]
  assert.equal(resolveQueueSelection({ items, currentId: 'A', preferredId: 'A', nextId: 'C' }), 'C')
})

test('first load without a prior selection chooses one deterministic valid item', () => {
  const items = [{ id: 'A' }, { id: 'B' }]
  assert.equal(resolveQueueSelection({ items, nextId: 'B' }), 'B')
})

test('valid routed selection wins and invalid restoration falls back', () => {
  const items = [{ id: 'A' }, { id: 'B' }]
  assert.equal(resolveQueueSelection({ items, preferredId: 'A', nextId: 'B' }), 'A')
  assert.equal(resolveQueueSelection({ items, preferredId: 'missing', nextId: 'B' }), 'B')
})

test('list refresh retains a valid current identity instead of attaching stale detail', () => {
  const items = [{ id: 'A', title: 'fresh A' }, { id: 'B', title: 'fresh B' }]
  const id = resolveQueueSelection({ items, currentId: 'B' })
  assert.equal(id, 'B')
  assert.equal(items.find(item => item.id === id).title, 'fresh B')
})

test('a background refresh keeps an already-loaded rich item instead of collapsing it to a compact row', () => {
  const current = [
    { id: 'A', status: 'done', record_hash: 'h1', detail_loaded: true, pipeline: { nodes: [{ id: 'n1' }] }, run_artifacts: [{ path: 'x' }] },
  ]
  const fresh = [
    { id: 'A', status: 'done', record_hash: 'h1', detail_loaded: false },
  ]
  const merged = mergeRefreshedQueueItems(current, fresh)
  assert.equal(merged[0].detail_loaded, true)
  assert.deepEqual(merged[0].pipeline, { nodes: [{ id: 'n1' }] })
  assert.deepEqual(merged[0].run_artifacts, [{ path: 'x' }])
})

test('a background refresh drops stale rich detail once the record hash actually changes', () => {
  const current = [
    { id: 'A', status: 'agent_working', record_hash: 'h1', detail_loaded: true, pipeline: { nodes: [{ id: 'n1' }] } },
  ]
  const fresh = [
    { id: 'A', status: 'done', record_hash: 'h2', detail_loaded: false },
  ]
  const merged = mergeRefreshedQueueItems(current, fresh)
  assert.equal(merged[0].detail_loaded, false)
  assert.equal(merged[0].pipeline, undefined)
  assert.equal(merged[0].status, 'done')
})

test('a background refresh does not fabricate rows for items that disappeared, or drop new ones', () => {
  const current = [{ id: 'A', record_hash: 'h1', detail_loaded: true }]
  const fresh = [{ id: 'B', record_hash: 'h2', detail_loaded: false }]
  const merged = mergeRefreshedQueueItems(current, fresh)
  assert.deepEqual(merged.map(item => item.id), ['B'])
})

test('resolvePrimaryDeliverable prefers a completed workflow final artifact over a run artifact', () => {
  const result = resolvePrimaryDeliverable({
    finalArtifact: { path: 'workflows/final.md', available: true },
    primaryArtifact: { path: 'results/primary.md', available: true },
    runArtifacts: [{ path: 'results/primary.md', available: true }, { path: 'results/other.md', available: true }],
    latestReceiptPath: 'queue/receipts/x.md',
  })
  assert.equal(result.primary.path, 'workflows/final.md')
  assert.deepEqual(result.deliverables.map(item => item.path), ['results/primary.md', 'results/other.md'])
})

test('resolvePrimaryDeliverable falls back to the first available non-receipt run artifact', () => {
  const result = resolvePrimaryDeliverable({
    finalArtifact: null,
    primaryArtifact: null,
    runArtifacts: [
      { path: 'queue/receipts/x.md', available: true },
      { path: 'results/report.md', available: true },
      { path: 'results/unavailable.md', available: false },
    ],
    latestReceiptPath: 'queue/receipts/x.md',
  })
  assert.equal(result.primary.path, 'results/report.md')
  assert.deepEqual(result.deliverables, [])
})

test('resolvePrimaryDeliverable never claims a deliverable exists when nothing is available', () => {
  const result = resolvePrimaryDeliverable({ finalArtifact: null, primaryArtifact: { path: 'x', available: false }, runArtifacts: [] })
  assert.equal(result.primary, null)
  assert.deepEqual(result.deliverables, [])
})

test('resolvePrimaryDeliverable de-duplicates the same path appearing in multiple sources', () => {
  const result = resolvePrimaryDeliverable({
    finalArtifact: { path: 'results/report.md', available: true },
    primaryArtifact: { path: 'results/report.md', available: true },
    runArtifacts: [{ path: 'results/report.md', available: true }],
  })
  assert.equal(result.primary.path, 'results/report.md')
  assert.deepEqual(result.deliverables, [])
})

test('classifyArtifact distinguishes business results, workflow support, and execution evidence', () => {
  assert.equal(classifyArtifact({ path: 'workflows/internal_outreach_daily/workflow.md' }), 'workflow_supporting')
  assert.equal(classifyArtifact({ path: 'skills/internal_outreach_daily/SKILL.md' }), 'workflow_supporting')
  assert.equal(classifyArtifact({ path: 'queue/receipts/AOS-2026-0001.md' }), 'execution_evidence')
  assert.equal(classifyArtifact({ path: 'logs/dashboard_backend.log' }), 'execution_evidence')
  assert.equal(classifyArtifact({ path: 'workflows/queue_artifacts/AOS-2026-0498_Run_Internal_Outreach_Daily.md' }), 'business_result')
  assert.equal(classifyArtifact({ path: 'results/report.md' }), 'business_result')
})

test('resolvePrimaryDeliverable prefers a generated business artifact over the workflow definition file it followed', () => {
  const result = resolvePrimaryDeliverable({
    finalArtifact: null,
    primaryArtifact: { path: 'workflows/internal_outreach_daily/workflow.md', available: true },
    runArtifacts: [
      { path: 'queue/receipts/AOS-2026-0498.md', available: true },
      { path: 'workflows/internal_outreach_daily/workflow.md', available: true },
      { path: 'workflows/queue_artifacts/AOS-2026-0498_Run_Internal_Outreach_Daily.md', available: true },
    ],
    latestReceiptPath: 'queue/receipts/AOS-2026-0498.md',
  })
  assert.equal(result.primary.path, 'workflows/queue_artifacts/AOS-2026-0498_Run_Internal_Outreach_Daily.md')
  assert.ok(!result.deliverables.some(item => item.path.endsWith('workflow.md')))
})

test('resolvePrimaryDeliverable never lets an execution receipt outrank an available generated report', () => {
  const result = resolvePrimaryDeliverable({
    runArtifacts: [
      { path: 'queue/receipts/AOS-2026-0011.md', available: true },
      { path: 'results/final_review_package.md', available: true },
    ],
  })
  assert.equal(result.primary.path, 'results/final_review_package.md')
})

test('groupWorkflowChildren folds an executive-objective child into its parent as a single top-level entry', () => {
  const items = [
    { id: 'AOS-2026-0497', title: 'Run Internal Outreach Daily to verified no-send outcome', status: 'done', owner: 'hermes', parent_id: null, updated_at: '2026-09-12T01:57:59Z' },
    { id: 'AOS-2026-0498', title: 'Run Internal Outreach Daily', status: 'done', owner: 'revenue', parent_id: 'AOS-2026-0497', step_index: 1, updated_at: '2026-09-12T01:57:24Z' },
    { id: 'AOS-2026-0700', title: 'Unrelated item', status: 'done', owner: 'delivery', parent_id: null, updated_at: '2026-09-10T09:00:00Z' },
  ]
  const grouped = groupWorkflowChildren(items)
  assert.deepEqual(grouped.map(item => item.id), ['AOS-2026-0497', 'AOS-2026-0700'])
  assert.equal(grouped[0].childSteps.length, 1)
  assert.equal(grouped[0].childSteps[0].id, 'AOS-2026-0498')
})

test('groupWorkflowChildren leaves a child standalone when its parent is not present in the list', () => {
  const items = [{ id: 'AOS-2026-0498', title: 'Orphaned child', status: 'done', parent_id: 'AOS-2026-9999' }]
  const grouped = groupWorkflowChildren(items)
  assert.deepEqual(grouped.map(item => item.id), ['AOS-2026-0498'])
})

test('groupEntryMatches surfaces a grouped card when only a folded child matches the filter', () => {
  const parent = {
    id: 'AOS-2026-0497', owner: 'hermes',
    childSteps: [{ id: 'AOS-2026-0498', owner: 'revenue' }],
  }
  const matchesRevenue = row => row.owner === 'revenue'
  assert.equal(groupEntryMatches(parent, matchesRevenue), true)
  assert.equal(groupEntryMatches(parent, row => row.owner === 'marketing'), false)
})

test('richListOutcomeLine extracts a deterministic count from a folded child\'s already-loaded artifact content', () => {
  const reportMarkdown = [
    '# AOS-2026-0498 — Internal Outreach Daily local no-send review package',
    '## Selected outreach candidates',
    '### 1. Nicolas Dupont — Cyborg',
    '### 2. Parminder Singh — DeepInspect.AI',
    '### 3. Ilan Puterman — Club Hub',
    'Zero sends: confirmed.',
  ].join('\n')
  const parent = {
    id: 'AOS-2026-0497',
    summary_for_operator: 'Executive result',
    childSteps: [{ id: 'AOS-2026-0498', primary_artifact: { path: 'workflows/queue_artifacts/AOS-2026-0498_report.md', content: reportMarkdown } }],
  }
  assert.equal(richListOutcomeLine(parent), '3 outreach candidates selected · No-send review ready')
})

test('richListOutcomeLine falls back to the compact summary when no rich artifact content is cached', () => {
  assert.equal(richListOutcomeLine({ summary_for_operator: 'Ran locally, no external action.' }), 'Ran locally, no external action.')
  assert.equal(richListOutcomeLine({}), '')
})

test('detectRequestedDeliveryChannel finds a named channel only alongside delivery language', () => {
  assert.equal(detectRequestedDeliveryChannel('Please send me a Telegram message with the file attached.'), 'telegram')
  assert.equal(detectRequestedDeliveryChannel('Run the Telegram bridge health check.'), null)
  assert.equal(detectRequestedDeliveryChannel('Run the Internal Outreach Daily workflow for me.'), null)
})

test('resolveRequestedDeliveryStatus never invents a status when the item never requested delivery', () => {
  assert.equal(resolveRequestedDeliveryStatus({ context: 'Run the Internal Outreach Daily workflow to completion.' }), null)
})

test('resolveRequestedDeliveryStatus distinguishes an honored request from a silently dropped one', () => {
  const requested = { context: 'Send me a Telegram message with the .md file attached.', summary_for_operator: 'Report generated.' }
  assert.deepEqual(resolveRequestedDeliveryStatus(requested), { channel: 'telegram', completed: false })
  const delivered = { ...requested, summary_for_operator: 'Report generated and the Telegram message was sent.' }
  assert.deepEqual(resolveRequestedDeliveryStatus(delivered), { channel: 'telegram', completed: true })
})

test('resolveArtifactBaseName prefers the queue item title over an AOS-ID-shaped filename', () => {
  const base = resolveArtifactBaseName({
    ref: { path: 'workflows/queue_artifacts/AOS-2026-0498_Run_Internal_Outreach_Daily.md' },
    queueItemTitle: 'Run Internal Outreach Daily',
  })
  assert.equal(base, 'Run Internal Outreach Daily')
})

test('resolveArtifactBaseName falls back to the cleaned filename when no queue item title exists', () => {
  assert.equal(resolveArtifactBaseName({ ref: { path: 'results/quarterly_report.md' } }), 'Quarterly Report')
})

test('resolveArtifactTabTitle appends a role word derived from artifact classification', () => {
  const title = resolveArtifactTabTitle({
    ref: { path: 'workflows/queue_artifacts/AOS-2026-0498_Run_Internal_Outreach_Daily.md' },
    queueItemTitle: 'Internal Outreach Daily',
  })
  assert.equal(title, 'Internal Outreach Daily — Report')
})

test('resolveArtifactTabTitle labels a receipt as evidence rather than an AOS ID', () => {
  const title = resolveArtifactTabTitle({
    ref: { path: 'queue/receipts/AOS-2026-0498.md' },
    queueItemTitle: 'Internal Outreach Daily',
  })
  assert.equal(title, 'Internal Outreach Daily — Evidence')
})

test('deliverableDisplayLabel marks the primary result distinctly from secondary deliverables', () => {
  const ref = { path: 'workflows/queue_artifacts/AOS-2026-0497_executive_outcome.md' }
  assert.equal(deliverableDisplayLabel(ref, { queueItemTitle: 'Internal Outreach Daily', isPrimary: true }), '★ Internal Outreach Daily — Summary')
  assert.equal(deliverableDisplayLabel(ref, { queueItemTitle: 'Internal Outreach Daily' }), 'Internal Outreach Daily — Summary')
})

test('artifact tab state persists open tabs, active tab, and enough identity to reopen them, never raw content', () => {
  const storage = fakeStorage()
  const tabs = [
    { id: 'results/report.md', path: 'results/report.md', label: 'Report', category: 'Artifact', extension: '.md', content: 'huge content should not persist', loading: false },
  ]
  persistArtifactTabs(storage, tabs, 'results/report.md')
  const restored = loadPersistedArtifactTabs(storage)
  assert.deepEqual(restored.tabs, [{ id: 'results/report.md', path: 'results/report.md', label: 'Report', category: 'Artifact', extension: '.md' }])
  assert.equal(restored.activeContentTab, 'results/report.md')
  assert.equal('content' in JSON.parse(storage._data['aos.dashboard.queue.tabs.v1']).tabs[0], false)
})

test('artifact tab state restore never crashes on missing or corrupt storage', () => {
  assert.deepEqual(loadPersistedArtifactTabs(undefined), { tabs: [], activeContentTab: 'overview' })
  assert.deepEqual(loadPersistedArtifactTabs(fakeStorage({ 'aos.dashboard.queue.tabs.v1': 'not json' })), { tabs: [], activeContentTab: 'overview' })
})

test('accordion state is keyed by work item ID and defaults to collapsed', () => {
  const storage = fakeStorage()
  assert.deepEqual(loadAccordionState(storage, 'AOS-2026-0001'), DEFAULT_ACCORDION_STATE)
  persistAccordionState(storage, 'AOS-2026-0001', { workflow: true, technical: true, receipts: false })
  assert.deepEqual(loadAccordionState(storage, 'AOS-2026-0001'), { workflow: true, technical: true, receipts: false })
  // A different item's state stays independent (and still defaults collapsed).
  assert.deepEqual(loadAccordionState(storage, 'AOS-2026-0002'), DEFAULT_ACCORDION_STATE)
})

test('accordion state persistence never throws when storage is unavailable', () => {
  assert.doesNotThrow(() => persistAccordionState(undefined, 'AOS-2026-0001', { workflow: true, technical: false, receipts: false }))
  assert.doesNotThrow(() => persistAccordionState(fakeStorage(), '', { workflow: true, technical: false, receipts: false }))
})
