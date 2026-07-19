import assert from 'node:assert/strict'
import test from 'node:test'
import { buildLaneWorkspace, defaultLaneFilter, laneFilterCounts, laneScopedItems, queueItemLane, sortLaneItems } from '../src/laneWorkspaceState.js'

const item = (id, status, lane, updated_at) => ({ id, status, lane, updated_at, title: id })

const fixtures = [
  item('OPS-REVIEW-OLD', 'human_review', 'operations', '2026-07-18T09:00:00Z'),
  item('OPS-REVIEW-NEW', 'needs_input', 'operations', '2026-07-18T10:00:00Z'),
  item('OPS-READY-OLD', 'inbox', 'operations', '2026-07-18T11:00:00Z'),
  item('OPS-READY-NEW', 'agent_todo', 'operations', '2026-07-18T12:00:00Z'),
  item('OPS-BLOCKED', 'blocked', 'operations', '2026-07-18T13:00:00Z'),
  item('OPS-RUNNING', 'agent_working', 'operations', '2026-07-18T14:00:00Z'),
  item('OPS-DONE', 'done', 'operations', '2026-07-18T15:00:00Z'),
  item('OPS-CANCELLED', 'cancelled', 'operations', '2026-07-18T16:00:00Z'),
  item('MKT-REVIEW', 'human_review', 'marketing', '2026-07-18T17:00:00Z'),
]

test('lane scoping honors tags, lane, owner, aliases, and unassigned fallback', () => {
  assert.equal(queueItemLane({ tags: ['lane:marketing'], lane: 'operations' }), 'marketing')
  assert.equal(queueItemLane({ lane: 'ops' }), 'operations')
  assert.equal(queueItemLane({ owner: 'delivery' }), 'delivery')
  assert.equal(queueItemLane({ owner: 'codex' }), 'unassigned')
  assert.deepEqual(laneScopedItems(fixtures, 'marketing').map(row => row.id), ['MKT-REVIEW'])
})

test('all six counts are lane-scoped and keep history explicit', () => {
  const scoped = laneScopedItems(fixtures, 'operations')
  assert.deepEqual(laneFilterCounts(scoped), {
    needs_me: 2,
    to_run: 2,
    blocked: 1,
    all_active: 6,
    done: 1,
    cancelled: 1,
  })
})

test('default is Needs Me only when that lane has Needs Me work', () => {
  assert.equal(defaultLaneFilter(laneScopedItems(fixtures, 'operations')), 'needs_me')
  assert.equal(defaultLaneFilter([item('READY', 'agent_todo', 'delivery')]), 'all_active')
  assert.equal(defaultLaneFilter([]), 'all_active')
})

test('sort groups Needs Me, ready, blocked, then other work with newest first inside each group', () => {
  const active = laneScopedItems(fixtures, 'operations').filter(row => !['done', 'cancelled'].includes(row.status))
  assert.deepEqual(sortLaneItems(active).map(row => row.id), [
    'OPS-REVIEW-NEW',
    'OPS-REVIEW-OLD',
    'OPS-READY-NEW',
    'OPS-READY-OLD',
    'OPS-BLOCKED',
    'OPS-RUNNING',
  ])
})

test('workspace applies defaults and explicit terminal filters without leaking another lane', () => {
  const defaultWorkspace = buildLaneWorkspace(fixtures, 'operations')
  assert.equal(defaultWorkspace.activeFilter, 'needs_me')
  assert.deepEqual(defaultWorkspace.items.map(row => row.id), ['OPS-REVIEW-NEW', 'OPS-REVIEW-OLD'])

  const cancelledWorkspace = buildLaneWorkspace(fixtures, 'operations', 'cancelled')
  assert.equal(cancelledWorkspace.activeFilter, 'cancelled')
  assert.deepEqual(cancelledWorkspace.items.map(row => row.id), ['OPS-CANCELLED'])
})
