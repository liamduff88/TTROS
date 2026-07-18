// Revisit: when Work Queue session scope behavior changes. · Last touched: 2026-07-18.
import assert from 'node:assert/strict'
import test from 'node:test'
import { loadQueueScope, normalizedQueueScope, persistQueueScope } from '../src/queueState.js'

test('queue scope defaults to Active and persists valid session choices', () => {
  const values = new Map()
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  }

  assert.equal(loadQueueScope(storage), 'active')
  assert.equal(persistQueueScope('history', storage), 'history')
  assert.equal(loadQueueScope(storage), 'history')
  assert.equal(persistQueueScope('all', storage), 'all')
  assert.equal(loadQueueScope(storage), 'all')
  assert.equal(normalizedQueueScope('invalid'), 'active')
})
