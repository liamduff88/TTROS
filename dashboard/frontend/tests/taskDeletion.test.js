import test from 'node:test'
import assert from 'node:assert/strict'
import { canSubmitTaskDeletion, selectionAfterTaskDeletion, taskDeletionFailureMessage } from '../src/queueState.js'

test('destructive submission requires a reason and the exact selected AOS ID', () => {
  const base = { itemId: 'AOS-2026-9001', reason: 'Safe fixture cleanup', submitting: false }
  assert.equal(canSubmitTaskDeletion({ ...base, confirmation: '' }), false)
  assert.equal(canSubmitTaskDeletion({ ...base, confirmation: 'AOS-2026-9002' }), false)
  assert.equal(canSubmitTaskDeletion({ ...base, confirmation: base.itemId }), true)
  assert.equal(canSubmitTaskDeletion({ ...base, confirmation: base.itemId, reason: 'x'.repeat(241) }), false)
  assert.equal(canSubmitTaskDeletion({ ...base, confirmation: base.itemId, submitting: true }), false)
})

test('successful deletion removes the card and selects the adjacent suitable item', () => {
  const items = [{ id: 'A' }, { id: 'B' }, { id: 'C' }]
  assert.deepEqual(selectionAfterTaskDeletion(items, 'B'), { items: [{ id: 'A' }, { id: 'C' }], selectedId: 'C' })
  assert.deepEqual(selectionAfterTaskDeletion(items, 'C'), { items: [{ id: 'A' }, { id: 'B' }], selectedId: 'B' })
  assert.deepEqual(selectionAfterTaskDeletion([{ id: 'A' }], 'A'), { items: [], selectedId: null })
})

test('dependent blocker messages preserve the exact blocking IDs', () => {
  const message = taskDeletionFailureMessage({
    code: 'active_dependents',
    message: 'Task is required by nonterminal work.',
    blockers: { dependent_ids: ['AOS-2026-9002', 'AOS-2026-9003'] },
  })
  assert.match(message, /AOS-2026-9002, AOS-2026-9003/)
  assert.match(message, /required by nonterminal work/)
})

test('honest failure formatting does not fabricate success or hide plain backend errors', () => {
  assert.equal(taskDeletionFailureMessage('Queue lock timed out.'), 'Queue lock timed out.')
  assert.match(taskDeletionFailureMessage(null), /failed/)
})
