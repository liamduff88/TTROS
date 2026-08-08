// Revisit: when Work Queue deletion confirmation or replay behavior changes. · Last touched: 2026-08-04.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseUrl = process.env.TASK_DELETION_BASE_URL || 'http://127.0.0.1:3010'
const screenshotPath = process.env.TASK_DELETION_SCREENSHOT
if (!screenshotPath) throw new Error('TASK_DELETION_SCREENSHOT is required')

const ids = {
  eligible: 'AOS-2026-9901',
  next: 'AOS-2026-9902',
  target: 'AOS-2026-9903',
  dependent: 'AOS-2026-9904',
  running: 'AOS-2026-9905',
  stale: 'AOS-2026-9906',
  protected: 'AOS-2026-0071',
}
const hash = value => value.repeat(64).slice(0, 64)
let items = [
  { id: ids.eligible, title: 'Disposable browser deletion fixture', status: 'blocked', owner: 'operations', priority: 100, record_hash: hash('a') },
  { id: ids.next, title: 'Next suitable task', status: 'agent_todo', owner: 'codex', priority: 90, record_hash: hash('b') },
  { id: ids.target, title: 'Dependency target fixture', status: 'blocked', owner: 'operations', priority: 80, record_hash: hash('c') },
  { id: ids.dependent, title: 'Blocking dependent fixture', status: 'agent_todo', owner: 'operations', priority: 70, record_hash: hash('d') },
  { id: ids.running, title: 'Running deletion fixture', status: 'agent_working', owner: 'codex', priority: 60, record_hash: hash('e') },
  { id: ids.stale, title: 'Stale deletion fixture', status: 'blocked', owner: 'operations', priority: 50, record_hash: hash('f') },
  { id: ids.protected, title: 'Immutable protected item', status: 'done', owner: 'hermes', priority: 1, record_hash: hash('1') },
].map((item, index) => ({
  ...item,
  created_at: `2026-08-04T10:0${index}:00Z`,
  updated_at: `2026-08-04T10:0${index}:00Z`,
  detail_loaded: false,
}))

const statuses = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled']
const activeStatuses = new Set(statuses.filter(status => !['done', 'cancelled'].includes(status)))
const counts = () => Object.fromEntries(statuses.map(status => [status, items.filter(item => item.status === status).length]))
const scoped = scope => items.filter(item => scope === 'active' ? activeStatuses.has(item.status) : scope === 'history' ? !activeStatuses.has(item.status) : true)
const response = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } })
let deleteCalls = 0
let tombstoneCount = 0
let deletedRequest = null
await page.addInitScript(() => {
  sessionStorage.setItem('aos.dashboard.queue-scope.v1', 'all')
  sessionStorage.setItem('aos.dashboard.shell.v1', JSON.stringify({
    view: 'work-queue',
    viewParams: {},
    sessionTabs: [
      { id: 'cockpit', label: 'Cockpit', workbench: 'hermes', preview: false },
      { id: 'work-queue', label: 'Work Queue', workbench: 'codex', preview: true, params: {} },
    ],
  }))
})

await page.route('**/api/**', async route => {
  const request = route.request()
  const url = new URL(request.url())
  if (url.pathname === '/api/queue/items' && request.method() === 'GET') {
    const scope = url.searchParams.get('scope') || 'all'
    const rows = scoped(scope)
    await route.fulfill(response({ success: true, scope, items: rows, itemCount: rows.length, totalCount: items.length }))
    return
  }
  if (['/api/queue/status', '/api/queue/summary'].includes(url.pathname)) {
    const active = scoped('active')
    await route.fulfill(response({
      success: true, counts: counts(), totalCount: items.length, activeCount: active.length,
      needsLiam: active.filter(item => ['needs_input', 'human_review', 'blocked'].includes(item.status)).length,
      nextItem: active[0] || null,
    }))
    return
  }
  const match = url.pathname.match(/^\/api\/queue\/items\/([^/]+)$/)
  if (match && request.method() === 'GET') {
    const item = items.find(row => row.id === decodeURIComponent(match[1]))
    await route.fulfill(response(item ? {
      success: true,
      item: { ...item, detail_loaded: true, depends_on: item.id === ids.dependent ? [ids.target] : [], tags: [], receipts: [], run_artifacts: [], pipeline: { nodes: [] } },
    } : { detail: 'queue item not found' }, item ? 200 : 404))
    return
  }
  if (match && request.method() === 'DELETE') {
    deleteCalls += 1
    const id = decodeURIComponent(match[1])
    const body = request.postDataJSON()
    await new Promise(resolve => setTimeout(resolve, 80))
    if (id === ids.target) {
      await route.fulfill(response({ detail: { code: 'active_dependents', message: `${id} is required by nonterminal queue work.`, blockers: { dependent_ids: [ids.dependent] } } }, 409))
      return
    }
    if (id === ids.running) {
      await route.fulfill(response({ detail: { code: 'agent_working', message: `${id} is running; cancel or stop it first.`, blockers: { action: 'cancel_or_stop_first' } } }, 409))
      return
    }
    if (id === ids.stale) {
      await route.fulfill(response({ detail: { code: 'stale_queue_state', message: `${id} changed after deletion was opened; refresh and review it again.`, blockers: {} } }, 409))
      return
    }
    if (id === ids.protected) {
      await route.fulfill(response({ detail: { code: 'immutable_item', message: `${id} is permanently protected and cannot be deleted.`, blockers: { protected_item_id: id } } }, 403))
      return
    }
    if (deletedRequest?.request_id === body.request_id) {
      await route.fulfill(response({
        ok: true, success: true, deleted_item_id: id, deleted_at: deletedRequest.deleted_at,
        tombstone_reference: deletedRequest.tombstone_reference, counts: counts(), total_count: items.length,
        idempotency: { request_id: body.request_id, replayed: true },
      }))
      return
    }
    assert.equal(id, ids.eligible)
    assert.equal(body.expected_record_hash, hash('a'))
    items = items.filter(item => item.id !== id)
    tombstoneCount += 1
    deletedRequest = {
      ...body,
      deleted_at: '2026-08-04T11:00:00Z',
      tombstone_reference: `queue/receipts/task-deletion-${body.request_id}.json`,
    }
    await route.fulfill(response({
      ok: true, success: true, deleted_item_id: id, deleted_at: deletedRequest.deleted_at,
      tombstone_reference: deletedRequest.tombstone_reference, counts: counts(), total_count: items.length,
      idempotency: { request_id: body.request_id, replayed: false },
    }))
    return
  }
  await route.fulfill(response({ success: true, counts: counts(), queue_items: items, needs_me: [] }))
})

const openDelete = async id => {
  await page.locator(`[data-queue-card-id="${id}"]`).click()
  await page.getByTestId('open-task-deletion').click()
  const dialog = page.getByTestId('task-deletion-dialog')
  await dialog.waitFor()
  assert.equal(await page.getByTestId('task-deletion-item-id').innerText(), id)
  return dialog
}
const fillDelete = async (dialog, id, reason = 'Safe fixture cleanup') => {
  await dialog.getByTestId('task-deletion-reason').fill(reason)
  await dialog.getByTestId('task-deletion-confirmation').fill(id)
}
const expectBlocker = async (id, expectedText) => {
  const dialog = await openDelete(id)
  await fillDelete(dialog, id)
  await dialog.getByTestId('confirm-task-deletion').click()
  await page.getByTestId('task-deletion-notice').waitFor()
  assert.match(await page.getByTestId('task-deletion-notice').innerText(), expectedText)
  assert.equal(await page.locator(`[data-queue-card-id="${id}"]`).count(), 1)
}

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  const dialog = await openDelete(ids.eligible)
  assert.equal(await page.getByTestId('task-deletion-item-title').innerText(), 'Disposable browser deletion fixture')
  await fillDelete(dialog, ids.eligible)
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  assert.equal(deleteCalls, 0)
  assert.equal(await page.locator(`[data-queue-card-id="${ids.eligible}"]`).count(), 1)

  const confirmed = await openDelete(ids.eligible)
  await fillDelete(confirmed, ids.eligible)
  await page.screenshot({ path: screenshotPath, fullPage: true })
  await confirmed.evaluate(form => {
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
  })
  await page.getByTestId('task-deletion-dialog').waitFor({ state: 'detached' })
  assert.equal(deleteCalls, 1)
  const doubleSubmitCalls = deleteCalls
  assert.equal(tombstoneCount, 1)
  assert.equal(await page.locator(`[data-queue-card-id="${ids.eligible}"]`).count(), 0)
  assert.equal(await page.getByTestId('queue-selected-detail').getAttribute('data-selected-item-id'), ids.next)
  assert.notEqual(await page.evaluate(() => performance.getEntriesByType('navigation')[0]?.type), 'reload')
  assert.match(await page.getByTestId('task-deletion-notice').innerText(), /permanently removed/)

  const replay = await page.evaluate(async ({ id, body }) => {
    const response = await fetch(`/api/queue/items/${id}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    return { status: response.status, body: await response.json() }
  }, { id: ids.eligible, body: { expected_record_hash: hash('a'), deletion_reason: deletedRequest.deletion_reason, request_id: deletedRequest.request_id } })
  assert.equal(replay.status, 200)
  assert.equal(replay.body.idempotency.replayed, true)
  assert.equal(tombstoneCount, 1)

  await expectBlocker(ids.target, new RegExp(ids.dependent))
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expectBlocker(ids.running, /cancel or stop it first/i)
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expectBlocker(ids.stale, /changed after deletion was opened/i)
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expectBlocker(ids.protected, /permanently protected/i)

  process.stdout.write(`${JSON.stringify({
    success: true,
    confirmation_cancelled_without_request: true,
    deleted_without_reload: true,
    selected_next_item: ids.next,
    double_submit_delete_calls: doubleSubmitCalls,
    idempotent_replay: replay.body.idempotency.replayed,
    tombstone_count: tombstoneCount,
    blocker_ids: { dependent: ids.dependent, running: ids.running, stale: ids.stale, protected: ids.protected },
    screenshot: screenshotPath,
  }, null, 2)}\n`)
} finally {
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
}
