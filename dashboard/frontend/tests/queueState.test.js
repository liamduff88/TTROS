import test from 'node:test'
import assert from 'node:assert/strict'
import { humanNeededItems, mergeQueueSummary, normalizeCockpitQueue, resolveQueueSelection } from '../src/queueState.js'

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
