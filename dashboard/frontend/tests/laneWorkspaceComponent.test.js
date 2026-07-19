import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

const count = (text, pattern) => (text.match(pattern) || []).length

test('lane workspace renders six scoped counts and reuses the compact review card', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { LaneWorkspaceContent } = await vite.ssrLoadModule('/src/views/LaneWorkspace.jsx')

  const workspace = {
    lane: 'operations',
    activeFilter: 'all_active',
    total: 4,
    counts: { needs_me: 2, to_run: 1, blocked: 1, all_active: 4, done: 0, cancelled: 0 },
    items: [
      { id: 'OPS-REVIEW', title: 'Review this', lane: 'operations', status: 'human_review' },
      { id: 'OPS-INPUT', title: 'Answer this', lane: 'operations', status: 'needs_input' },
      { id: 'OPS-READY', title: 'Run this', lane: 'operations', status: 'agent_todo' },
      { id: 'OPS-BLOCKED', title: 'Blocked work', lane: 'operations', status: 'blocked', blocked_reason: 'Waiting locally' },
    ],
  }
  const markup = renderToStaticMarkup(React.createElement(LaneWorkspaceContent, {
    workspace,
    loading: false,
    error: null,
    onFilterChange: () => {},
    onRefresh: () => {},
    onReviewSaved: () => {},
  }))

  assert.match(markup, /data-lane-workspace="operations"/)
  assert.equal(count(markup, /data-lane-filter="/g), 6)
  for (const [filter, value] of Object.entries(workspace.counts)) {
    assert.match(markup, new RegExp(`data-lane-filter-count="${filter}">${value}<`))
  }
  assert.equal(count(markup, /data-review-card-id="OPS-REVIEW"/g), 1)
  assert.equal(count(markup, /data-review-card-body/g), 1)
  assert.equal(markup.includes('data-review-card-body]]:hidden'), false)
  const reviewBody = markup.indexOf('data-review-card-body')
  const reviewCardEnd = markup.indexOf('</article>', reviewBody)
  const reviewActions = markup.indexOf('aria-label="Operator note for OPS-REVIEW"')
  assert.ok(reviewBody >= 0 && reviewCardEnd > reviewBody)
  assert.equal(reviewActions, -1)
  assert.equal(count(markup, /data-queue-card-id=/g), 3)
  assert.equal(count(markup, />Approve</g), 2)
  assert.equal(count(markup, />Needs changes</g), 2)
  assert.equal(count(markup, />Reject</g), 1)
  assert.equal(count(markup, />Block</g), 1)
  assert.match(markup, /data-queue-card-id="OPS-READY"/)
  assert.match(markup, /data-lane-action="run"/)
  assert.match(markup, />Run now<\/button>/)
  assert.match(markup, /data-lane-action="cancel"/)
  assert.match(markup, />Cancel<\/button>/)
  assert.match(markup, /data-lane-bulk-action="run"[^>]*>Run selected</)
  assert.match(markup, /data-lane-bulk-action="cancel"/)
  assert.match(markup, />Cancel selected<\/button>/)
  assert.match(markup, /data-queue-card-id="OPS-BLOCKED"/)
  assert.match(markup, /data-blocked-reason="OPS-BLOCKED">Waiting locally</)
  assert.match(markup, /data-lane-action="unblock"/)
  assert.match(markup, />Unblock<\/button>/)
  assert.equal(markup.includes('MKT-'), false)
})
