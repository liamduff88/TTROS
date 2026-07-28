import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import {
  applyReviewDecision,
  hasReviewDraft,
  isReviewCardItem,
  loadReviewDraft,
  persistReviewDraft,
  reviewDraftKey,
  saveReviewNoteDraft,
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

test('human-review card renders actual receipt, artifact, review facts, note save, and only explicit state actions', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { HumanReviewCard } = await vite.ssrLoadModule('/src/components/HumanReviewCard.jsx')
  const item = {
    id: 'ITEM-1', title: 'Readable review title', status: 'human_review', owner: 'codex',
    summary_for_operator: 'Substantive result ready.',
    latest_receipt: { path: 'queue/receipts/ITEM-1.md', content: 'PASS\nACTUAL RECEIPT BODY' },
    primary_artifact: { path: 'workflows/queue_artifacts/ITEM-1.md', content: 'CONSOLIDATED ARTIFACT BODY' },
    review_details: {
      summary: 'Substantive result ready.', worker: 'codex', attempts: 2,
      validation: 'Focused tests passed.', failure_explanation: '',
      token_usage_lines: ['Total input: 100', 'Cached input: 80', 'Non-cached input: 20', 'Output: 10'],
      receipt_content: 'PASS\nACTUAL RECEIPT BODY',
    },
  }
  const markup = renderToStaticMarkup(React.createElement(HumanReviewCard, { item }))

  assert.equal(count(markup, /data-review-card-id=/g), 1)
  assert.match(markup, /ACTUAL RECEIPT BODY/)
  assert.match(markup, /CONSOLIDATED ARTIFACT BODY/)
  assert.match(markup, /Substantive result ready/)
  assert.match(markup, /Focused tests passed/)
  assert.match(markup, /Total input: 100/)
  assert.match(markup, /Review note for ITEM-1/)
  assert.match(markup, />Save review note<\/button>/)
  assert.match(markup, />Approve<\/button>/)
  assert.match(markup, />Needs changes<\/button>/)
  assert.match(markup, />Block<\/button>/)
  assert.equal(markup.includes('Save/Attach'), false)
  assert.equal(markup.includes('Review-close status'), false)
  assert.equal(count(markup, /<select/g), 0)
})

test('saving a review note uses note endpoint semantics and preserves human_review', async () => {
  const storage = memoryStorage()
  const calls = []
  const draft = { note: 'Keep this exact review note' }
  const response = await saveReviewNoteDraft({
    itemId: 'ITEM-1', draft, storage,
    saveNote: async (...args) => {
      calls.push(args)
      return { success: true, ok: true, status: 'human_review', state_changed: false }
    },
  })
  assert.equal(response.status, 'human_review')
  assert.deepEqual(calls, [['ITEM-1', { review_note: draft.note }]])
  assert.equal(hasReviewDraft('ITEM-1', storage), false)
})

test('only approve requests done; changes and block use explicit existing paths', async () => {
  const calls = []
  const closeReview = async (...args) => { calls.push(args); return { success: true, ok: true } }
  await applyReviewDecision({ itemId: 'ITEM-1', decision: 'approve', note: '', closeReview })
  await applyReviewDecision({ itemId: 'ITEM-2', decision: 'needs_changes', note: 'Correct tests', closeReview })
  await applyReviewDecision({ itemId: 'ITEM-3', decision: 'block', note: 'Cannot accept', closeReview })
  assert.deepEqual(calls, [
    ['ITEM-1', { status: 'done', review_note: '', action: 'approve' }],
    ['ITEM-2', { status: 'needs_input', review_note: 'Correct tests', action: 'needs_changes' }],
    ['ITEM-3', { status: 'blocked', review_note: 'Cannot accept', action: 'block' }],
  ])
})

test('failed note save preserves the typed note and cards exist only for human_review', async () => {
  const storage = memoryStorage()
  const draft = { note: 'Do not lose this note' }
  await assert.rejects(saveReviewNoteDraft({
    itemId: 'ITEM-1', draft, storage,
    saveNote: async () => { throw new Error('simulated note failure') },
  }), /simulated note failure/)
  assert.deepEqual(loadReviewDraft('ITEM-1', storage), draft)
  assert.equal(storage.getItem(reviewDraftKey('ITEM-1')) !== null, true)
  assert.equal(isReviewCardItem({ id: 'ITEM-1', status: 'human_review' }, storage), true)
  assert.equal(isReviewCardItem({ id: 'ITEM-1', status: 'needs_input' }, storage), false)
  persistReviewDraft('ITEM-2', { note: 'separate' }, storage)
  assert.deepEqual(loadReviewDraft('ITEM-2', storage), { note: 'separate' })
})

test('outreach human-review card shows actionable prospect context and event controls without generic approval', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { HumanReviewCard } = await vite.ssrLoadModule('/src/components/HumanReviewCard.jsx')
  const item = {
    id: 'AOS-2026-0200', title: 'Loretta Davis — LinkedIn invitation ready', status: 'human_review',
    review_card_kind: 'outreach', detail_loaded: true,
    outreach_review: {
      prospect: { person_name: 'Loretta Davis', company_name: 'Talent Harbour Group' },
      channel: 'linkedin', stage: 'invitation_ready', due_date: null, score: 90,
      readiness: 'ready_for_linkedin_action_card', source_handoff: 'workflows/prospecting_daily_run/input/handoff.md',
      primary_signal: 'Post-acquisition operating signal.', main_caution: 'Complement existing systems.',
      exact_action: 'Send the connection invitation manually, then record invitation_sent.',
      profile_url: 'https://ca.linkedin.com/in/loretta-davis-72268312',
      copy: { linkedin_invitation: { body: 'Complete connection note.', active: true } },
      allowed_events: ['invitation_sent', 'reply_received', 'opt_out', 'cancelled'],
      manual_review_metadata: ['Manual LinkedIn-limit and role review required.'],
      reconciliation: { focused_review_question: 'Confirm no known prior contact.' },
    },
  }
  const markup = renderToStaticMarkup(React.createElement(HumanReviewCard, { item }))
  assert.match(markup, /data-review-card-kind="outreach"/)
  assert.match(markup, /Loretta Davis · Talent Harbour Group/)
  assert.match(markup, /Open exact public LinkedIn profile/)
  assert.match(markup, /Complete connection note\./)
  assert.match(markup, /Record actual outcome/)
  assert.match(markup, /invitation sent/)
  assert.equal(markup.includes('>Approve</button>'), false)
  assert.equal(markup.includes('>Needs changes</button>'), false)
})
