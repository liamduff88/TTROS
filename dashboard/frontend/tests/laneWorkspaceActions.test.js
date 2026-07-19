import assert from 'node:assert/strict'
import test from 'node:test'
import { cancellationReceiptText, performReadyAction, performReviewAction, performSelectedAction, selectedLaneItems, unblockLaneItem } from '../src/laneWorkspaceActions.js'

const ok = { success: true, ok: true }

test('review and input actions use the existing per-item review and receipt endpoints', async () => {
  const calls = []
  const endpoints = {
    closeReview: async (...args) => { calls.push(['review-close', ...args]); return ok },
    attachReceipt: async (...args) => { calls.push(['receipt', ...args]); return ok },
  }

  await performReviewAction({ id: 'REVIEW', status: 'human_review' }, 'approve', '', endpoints)
  await performReviewAction({ id: 'REVIEW', status: 'human_review' }, 'needs_changes', 'Revise this', endpoints)
  await performReviewAction({ id: 'REVIEW', status: 'human_review' }, 'reject', 'Not accepted', endpoints)
  await performReviewAction({ id: 'INPUT', status: 'needs_input' }, 'approve', 'Use this answer', endpoints)
  await performReviewAction({ id: 'INPUT', status: 'needs_input' }, 'needs_changes', 'Clarify this', endpoints)
  await performReviewAction({ id: 'INPUT', status: 'needs_input' }, 'reject', 'Cannot proceed', endpoints)

  assert.deepEqual(calls.slice(0, 3), [
    ['review-close', 'REVIEW', { status: 'done', review_note: '', action: 'approve' }],
    ['review-close', 'REVIEW', { status: 'needs_input', review_note: 'Revise this', action: 'needs_changes' }],
    ['review-close', 'REVIEW', { status: 'blocked', review_note: 'Not accepted', action: 'reject' }],
  ])
  assert.equal(calls[3][0], 'receipt')
  assert.equal(calls[3][1], 'INPUT')
  assert.equal(calls[3][2].status, 'agent_todo')
  assert.match(calls[3][2].receipt_text, /Use this answer/)
  assert.equal(calls[4][0], 'receipt')
  assert.equal(calls[4][2].status, 'needs_input')
  assert.match(calls[4][2].receipt_text, /Clarify this/)
  assert.equal(calls[5][0], 'receipt')
  assert.equal(calls[5][2].status, 'blocked')
  assert.match(calls[5][2].receipt_text, /Cannot proceed/)
})

test('run, cancel, and unblock use existing per-item endpoints and cancel attaches its receipt', async () => {
  const calls = []
  const endpoints = {
    runItem: async id => { calls.push(['run', id]); return ok },
    attachReceipt: async (...args) => { calls.push(['receipt', ...args]); return ok },
  }
  const item = { id: 'READY', status: 'agent_todo' }

  await performReadyAction(item, 'run', endpoints)
  await performReadyAction(item, 'cancel', endpoints)
  await unblockLaneItem({ id: 'BLOCKED', status: 'blocked' }, async (...args) => { calls.push(['status', ...args]); return ok })

  assert.deepEqual(calls[0], ['run', 'READY'])
  assert.equal(calls[1][0], 'receipt')
  assert.equal(calls[1][1], 'READY')
  assert.equal(calls[1][2].status, 'cancelled')
  assert.equal(calls[1][2].receipt_text, cancellationReceiptText(item))
  assert.deepEqual(calls[2], ['status', 'BLOCKED', 'agent_todo'])
})

test('current-filter selection excludes non-ready rows and selected runs are strictly sequential', async () => {
  const items = [
    { id: 'ONE', status: 'inbox' },
    { id: 'BLOCKED', status: 'blocked' },
    { id: 'TWO', status: 'agent_todo' },
  ]
  assert.deepEqual(selectedLaneItems(items, ['ONE', 'BLOCKED', 'TWO']).map(item => item.id), ['ONE', 'TWO'])

  const order = []
  let active = 0
  const endpoints = {
    runItem: async id => {
      active += 1
      assert.equal(active, 1)
      order.push(`start:${id}`)
      await new Promise(resolve => setTimeout(resolve, 5))
      order.push(`end:${id}`)
      active -= 1
      return ok
    },
  }
  const results = await performSelectedAction(selectedLaneItems(items, ['ONE', 'TWO']), 'run', endpoints)
  assert.deepEqual(order, ['start:ONE', 'end:ONE', 'start:TWO', 'end:TWO'])
  assert.deepEqual(results.map(result => [result.id, result.success]), [['ONE', true], ['TWO', true]])
})

test('selected cancellation calls the receipt endpoint once per item even when one fails', async () => {
  const calls = []
  const items = [{ id: 'ONE', status: 'inbox' }, { id: 'TWO', status: 'agent_todo' }]
  const results = await performSelectedAction(items, 'cancel', {
    attachReceipt: async (id, body) => {
      calls.push([id, body])
      if (id === 'ONE') throw new Error('first failed')
      return ok
    },
  })

  assert.deepEqual(calls.map(call => call[0]), ['ONE', 'TWO'])
  assert.ok(calls.every(([, body]) => body.status === 'cancelled' && /Queue cancellation:/.test(body.receipt_text)))
  assert.deepEqual(results.map(result => [result.id, result.success]), [['ONE', false], ['TWO', true]])
})
