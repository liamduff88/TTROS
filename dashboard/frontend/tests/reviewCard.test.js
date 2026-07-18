import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import {
  hasReviewDraft,
  isReviewCardItem,
  loadReviewDraft,
  persistReviewDraft,
  reviewDraftKey,
  saveReviewDraft,
} from '../src/reviewCardState.js'

const memoryStorage = () => {
  const values = new Map()
  return {
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  }
}

const count = (text, pattern) => (text.match(pattern) || []).length

test('one human-review item renders one minimal accessible card', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { HumanReviewCard } = await vite.ssrLoadModule('/src/components/HumanReviewCard.jsx')
  const item = { id: 'ITEM-1', title: 'Readable review title', status: 'human_review' }
  const markup = renderToStaticMarkup(React.createElement(HumanReviewCard, { item }))

  assert.equal(count(markup, /data-review-card-id=/g), 1)
  assert.match(markup, /ITEM-1<\/span> — Readable review title/)
  assert.equal(count(markup, /<textarea/g), 1)
  assert.equal(count(markup, /<select/g), 1)
  assert.equal(count(markup, /<button/g), 1)
  assert.match(markup, /Receipt for ITEM-1/)
  assert.match(markup, /Review-close status for ITEM-1/)
  assert.deepEqual([...markup.matchAll(/<option value="([^"]+)"/g)].map(match => match[1]), ['done', 'needs_input', 'blocked'])
  assert.match(markup, />Save\/Attach<\/button>/)

  for (const excluded of ['summary_for_operator', 'prompt', 'context', 'Artifacts', 'receipt path', 'transcript', 'test output', 'owner', 'lane', 'priority', 'tags', 'tokens', 'dependencies', '<details', 'SourceChip', 'StatusChip']) {
    assert.equal(markup.toLowerCase().includes(excluded.toLowerCase()), false, excluded)
  }
})

test('two review items render as two independent cards', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { HumanReviewCard } = await vite.ssrLoadModule('/src/components/HumanReviewCard.jsx')
  const items = [
    { id: 'ITEM-1', title: 'First title', status: 'human_review' },
    { id: 'ITEM-2', title: 'Second title', status: 'human_review' },
  ]
  const markup = renderToStaticMarkup(React.createElement('div', null, items.map(item => React.createElement(HumanReviewCard, { item, key: item.id }))))

  assert.equal(count(markup, /data-review-card-id=/g), items.length)
  assert.equal(count(markup, /<textarea/g), items.length)
  assert.equal(count(markup, /<select/g), items.length)
  assert.equal(count(markup, /<button/g), items.length)
})

test('save calls the existing close action once and keeps rail state across refresh', async () => {
  const storage = memoryStorage()
  const calls = []
  const draft = { receipt: 'Keep this exact receipt', status: 'needs_input' }
  const closeReview = async (...args) => {
    calls.push(args)
    return { success: true, ok: true, status: 'needs_input' }
  }

  await saveReviewDraft({ itemId: 'ITEM-1', draft, closeReview, storage })

  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0], ['ITEM-1', { status: 'needs_input', review_note: 'Keep this exact receipt' }])
  assert.deepEqual(loadReviewDraft('ITEM-1', storage), draft)
  assert.equal(isReviewCardItem({ id: 'ITEM-1', status: 'needs_input' }, storage), true)
})

test('done removes its card draft without affecting another review item', async () => {
  const storage = memoryStorage()
  persistReviewDraft('ITEM-1', { receipt: 'Close me', status: 'done' }, storage)
  persistReviewDraft('ITEM-2', { receipt: 'Leave me alone', status: 'blocked' }, storage)

  await saveReviewDraft({
    itemId: 'ITEM-1',
    draft: loadReviewDraft('ITEM-1', storage),
    closeReview: async () => ({ success: true, ok: true, status: 'done' }),
    storage,
  })

  assert.equal(hasReviewDraft('ITEM-1', storage), false)
  assert.deepEqual(loadReviewDraft('ITEM-2', storage), { receipt: 'Leave me alone', status: 'blocked' })
})

test('failed save preserves typed receipt and selected status', async () => {
  const storage = memoryStorage()
  const draft = { receipt: 'Do not lose this failure note', status: 'blocked' }

  await assert.rejects(
    saveReviewDraft({
      itemId: 'ITEM-1',
      draft,
      closeReview: async () => { throw new Error('simulated close failure') },
      storage,
    }),
    /simulated close failure/,
  )

  assert.equal(storage.getItem(reviewDraftKey('ITEM-1')) !== null, true)
  assert.deepEqual(loadReviewDraft('ITEM-1', storage), draft)
})
