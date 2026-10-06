// Revisit: when the Work Queue blocked-work attention panel or its actions change. · Last touched: 2026-10-06.
// Disposable in-browser queue (every /api/queue call is fulfilled here), so no
// click reaches the live queue. Proves each blocked-work action fires exactly
// one existing lifecycle call, never re-runs finished work, and never adds an item.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseUrl = process.env.BLOCKED_WORK_BASE_URL || 'http://127.0.0.1:3010'
const backendUrl = process.env.BLOCKED_WORK_BACKEND_URL || 'http://127.0.0.1:8010'
const shotDir = process.env.BLOCKED_WORK_SCREENSHOT_DIR
if (!shotDir) throw new Error('BLOCKED_WORK_SCREENSHOT_DIR is required')

const minutesAgo = minutes => new Date(Date.now() - minutes * 60000).toISOString().replace(/\.\d{3}Z$/, 'Z')
const objectiveStep = { category: 'system_failure', label: 'System problem', demands_operator: true, since: minutesAgo(18),
  reason: 'Paused by the spending safety check: token usage from an earlier model call could not be recorded, so further model calls were held back.',
  blocker_detail: 'Queue run failed before completion: Step 6 fuse paused', actions: ['dismiss'],
  retry_note: 'This is one step of a David objective; it cannot be re-run on its own, so the same work is never done twice.' }
const finished = { category: 'finished', label: 'Finished — not closed', demands_operator: false, since: minutesAgo(40),
  reason: 'The work finished and recorded a PASS result, but a later step stopped it from closing.', actions: ['close_finished', 'dismiss'],
  finished_evidence: { path: 'queue/receipts/AOS-PROOF-2003-worker.md', created_at: minutesAgo(42) } }
const retryable = { category: 'system_failure', label: 'System problem', demands_operator: true, since: minutesAgo(5),
  reason: 'The worker took too long and was stopped.', actions: ['retry', 'dismiss'], retry_note: '' }

const row = (id, title, status, attention, extra = {}) => ({ id, title, status, attention, owner: 'operations', priority: 5,
  created_at: minutesAgo(120), updated_at: attention?.since || minutesAgo(60), needs_me: [], detail_loaded: false, ...extra })
const items = [
  row('AOS-PROOF-2001', 'Proof objective with a blocked step', 'agent_working', null, { priority: 8 }),
  row('AOS-PROOF-2002', 'Blocked objective step', 'blocked', objectiveStep, { parent_id: 'AOS-PROOF-2001', step_index: 1 }),
  row('AOS-PROOF-2003', 'Work that finished before its block', 'blocked', finished, { priority: 7 }),
  row('AOS-PROOF-2004', 'Retryable timed-out work', 'blocked', retryable, { priority: 6 }),
]
const initialIds = items.map(item => item.id).sort()
const calls = []
const dismissed = reason => ({ category: 'dismissed', label: 'Dismissed', demands_operator: false, since: minutesAgo(0), reason, actions: [] })
const find = id => items.find(item => item.id === decodeURIComponent(id))
const json = value => ({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })
const statuses = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled']
const demands = item => ['blocked', 'needs_input', 'human_review'].includes(item.status) && item.attention?.demands_operator !== false
const summary = () => {
  const active = items.filter(item => !['done', 'cancelled'].includes(item.status))
  const needsMe = items.filter(demands)
  return { success: true, counts: Object.fromEntries(statuses.map(s => [s, items.filter(item => item.status === s).length])),
    totalCount: items.length, activeCount: active.length, needsLiam: needsMe.length, needsMeItems: needsMe, nextItem: active[0] || null }
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
await page.addInitScript(() => {
  sessionStorage.setItem('aos.dashboard.shell.v1', JSON.stringify({ view: 'work-queue', viewParams: {}, sessionTabs: [
    { id: 'cockpit', label: 'Cockpit', workbench: 'hermes', preview: false },
    { id: 'work-queue', label: 'Work Queue', workbench: 'codex', preview: true, params: {} },
  ] }))
})
await page.route('**/api/**', async route => {
  const request = route.request()
  const { pathname, search } = new URL(request.url())
  const method = request.method()
  if (pathname === '/api/queue/items' && method === 'GET') return route.fulfill(json({ success: true, scope: 'all', itemCount: items.length, totalCount: items.length, items }))
  if (['/api/queue/status', '/api/queue/summary'].includes(pathname)) return route.fulfill(json(summary()))
  if (pathname === '/api/dashboard/cockpit') return route.fulfill(json({ success: true, ...summary(), queue_items: items }))
  let match = pathname.match(/^\/api\/queue\/items\/([^/]+)$/)
  if (match && method === 'GET') return route.fulfill(json({ success: true, item: { ...find(match[1]), detail_loaded: true, receipts: [], run_artifacts: [], pipeline: null } }))
  match = pathname.match(/^\/api\/queue\/items\/([^/]+)\/(dismiss|close-finished|run|status|receipt|review-close)$/)
  if (match && method === 'POST') {
    const item = find(match[1])
    const body = request.postDataJSON() || {}
    calls.push({ action: match[2], id: item.id, body })
    if (match[2] === 'dismiss') {
      const closed = [item.id]
      item.status = 'cancelled'
      item.attention = dismissed(`Dismissed by Liam from the Work Queue: ${body.reason || 'No longer needed.'}`)
      const parent = items.find(other => other.id === item.parent_id)
      if (parent && items.filter(other => other.parent_id === parent.id).every(other => ['done', 'cancelled'].includes(other.status))) {
        parent.status = 'cancelled'
        parent.attention = dismissed(`Its remaining step ${item.id} was dismissed.`)
        closed.push(parent.id)
      }
      return route.fulfill(json({ ok: true, success: true, item_id: item.id, closed, item }))
    }
    if (match[2] === 'close-finished') {
      item.status = 'done'
      item.attention = null
      return route.fulfill(json({ ok: true, success: true, item_id: item.id, receipt_path: finished.finished_evidence.path, item }))
    }
    if (match[2] === 'run') {
      item.attention = { ...retryable, since: minutesAgo(0) }
      return route.fulfill(json({ ok: true, success: false, item_id: item.id, status: 'blocked' }))
    }
    return route.fulfill({ status: 500, body: `unexpected ${match[2]}` })
  }
  if (pathname.startsWith('/api/queue/') && method !== 'GET') {
    calls.push({ action: `unexpected ${method} ${pathname}` })
    return route.fulfill({ status: 500, body: 'unexpected mutation' })
  }
  const response = await route.fetch({ url: `${backendUrl}${pathname}${search}` })
  return route.fulfill({ response })
})

const panel = page.locator('[data-testid="attention-panel"]')
const notice = page.locator('[data-testid="attention-action-notice"]')
const select = async id => {
  await page.locator(`[data-queue-card-id="${id}"]`).click()
  await page.waitForFunction(target => document.querySelector('[data-testid="queue-selected-detail"]')?.getAttribute('data-selected-item-id') === target, id)
}
const needsMeText = () => page.locator('text=/Needs Me \\d+/').first().innerText()

await page.goto(baseUrl, { waitUntil: 'networkidle' })
await page.locator('[data-queue-card-id="AOS-PROOF-2001"]').waitFor()
assert.match(await needsMeText(), /Needs Me 2/, 'finished-but-not-closed work does not count as needing Liam')

// 1. A blocked objective step folded under a "working" parent: reason, timing, Dismiss only.
await select('AOS-PROOF-2001')
assert.equal(await panel.getAttribute('data-attention-target-id'), 'AOS-PROOF-2002')
assert.match(await panel.innerText(), /spending safety check/)
assert.match(await page.locator('[data-testid="attention-timing"]').innerText(), /^Blocked 1[78] min ago$/)
assert.equal(await page.locator('[data-testid="attention-retry"]').count(), 0)
assert.equal(await page.getByRole('button', { name: /Recover stuck worker|Worker running|Run again/ }).count(), 0, 'parent offers no misleading run button')
await page.locator('[data-testid="attention-dismiss"]').click()
await page.locator('[data-testid="attention-dismiss-reason"]').fill('Already completed in another session.')
await page.screenshot({ path: `${shotDir}/proof_dismiss_form.png` })
await page.locator('[data-testid="attention-dismiss-confirm"]').click()
await notice.filter({ hasText: 'Dismissed' }).waitFor()
await page.locator('[data-testid="attention-panel"][data-attention-category="dismissed"]').waitFor()
assert.match(await needsMeText(), /Needs Me 1/)

// 2. Finished-before-block work: Close as finished, never a re-run.
await select('AOS-PROOF-2003')
assert.equal(await panel.getAttribute('data-attention-category'), 'finished')
assert.equal(await page.getByRole('button', { name: /Run again|Rerun assigned worker/ }).count(), 0, 'finished work offers no re-run')
await page.screenshot({ path: `${shotDir}/proof_finished_before_close.png` })
await page.locator('[data-testid="attention-close-finished"]').click()
await notice.filter({ hasText: 'Closed as finished' }).waitFor()
assert.equal(await page.locator('[data-testid="attention-panel"]').count(), 0)

// 3. Retryable work: Retry is the existing run of the same item.
await select('AOS-PROOF-2004')
await page.locator('[data-testid="attention-retry"]').click()
await notice.filter({ hasText: 'stopped again' }).waitFor()
await page.screenshot({ path: `${shotDir}/proof_retry_stopped_again.png` })

assert.deepEqual(calls.map(call => `${call.action}:${call.id}`), [
  'dismiss:AOS-PROOF-2002', 'close-finished:AOS-PROOF-2003', 'run:AOS-PROOF-2004',
], 'each action made exactly one existing lifecycle call')
assert.equal(calls[0].body.reason, 'Already completed in another session.')
assert.deepEqual(items.map(item => item.id).sort(), initialIds, 'no item was created or removed')
assert.deepEqual(Object.fromEntries(items.map(item => [item.id, item.status])), {
  'AOS-PROOF-2001': 'cancelled', 'AOS-PROOF-2002': 'cancelled', 'AOS-PROOF-2003': 'done', 'AOS-PROOF-2004': 'blocked',
})
await browser.close()
console.log(JSON.stringify({ result: 'PASS', calls: calls.map(call => `${call.action}:${call.id}`), items: items.length }))
