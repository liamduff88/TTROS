// Revisit: when Work Queue scope or review-close browser contracts change. · Last touched: 2026-07-18.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseUrl = process.env.QUEUE_LIFECYCLE_BASE_URL || 'http://127.0.0.1:3010'
const backendUrl = process.env.QUEUE_LIFECYCLE_BACKEND_URL || 'http://127.0.0.1:8010'
const desktopPath = process.env.QUEUE_LIFECYCLE_DESKTOP_SCREENSHOT
const narrowPath = process.env.QUEUE_LIFECYCLE_NARROW_SCREENSHOT

if (!desktopPath || !narrowPath) throw new Error('Desktop and narrow screenshot paths are required')

const reviewId = 'AOS-PROOF-1001'
const activeId = 'AOS-PROOF-1002'
const oldDoneId = 'AOS-PROOF-1003'
const items = [
  { id: reviewId, title: 'Disposable lifecycle review proof', status: 'human_review', owner: 'codex', priority: 8, created_at: '2026-07-18T10:00:00Z', updated_at: '2026-07-18T10:00:00Z', detail_loaded: false },
  { id: activeId, title: 'Unaffected active detail proof', status: 'agent_todo', owner: 'codex', priority: 7, created_at: '2026-07-18T09:00:00Z', updated_at: '2026-07-18T09:00:00Z', detail_loaded: false },
  { id: oldDoneId, title: 'Existing terminal history proof', status: 'done', owner: 'hermes', priority: 5, created_at: '2026-07-17T09:00:00Z', updated_at: '2026-07-17T09:00:00Z', detail_loaded: false },
]

const activeStatuses = new Set(['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'blocked'])
const historyStatuses = new Set(['done', 'cancelled'])
const scoped = scope => items.filter(item => scope === 'active' ? activeStatuses.has(item.status) : scope === 'history' ? historyStatuses.has(item.status) : true)
const counts = () => Object.fromEntries(['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled'].map(status => [status, items.filter(item => item.status === status).length]))
const json = value => ({ status: 200, contentType: 'application/json', body: JSON.stringify(value) })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
let closeCalls = 0

await page.addInitScript(() => {
  if (!sessionStorage.getItem('aos.dashboard.shell.v1')) {
    sessionStorage.setItem('aos.dashboard.shell.v1', JSON.stringify({
      view: 'work-queue',
      viewParams: {},
      sessionTabs: [
        { id: 'cockpit', label: 'Cockpit', workbench: 'hermes', preview: false },
        { id: 'work-queue', label: 'Work Queue', workbench: 'codex', preview: true, params: {} },
      ],
    }))
  }
})

await page.route('**/api/**', async route => {
  const request = route.request()
  const requested = new URL(request.url())
  if (requested.pathname === '/api/queue/items' && request.method() === 'GET') {
    const scope = requested.searchParams.get('scope') || 'all'
    const selected = scoped(scope)
    await route.fulfill(json({ success: true, scope, itemCount: selected.length, totalCount: items.length, diagnostics: { invalidRecordCount: 0 }, items: selected }))
    return
  }
  if ((requested.pathname === '/api/queue/status' || requested.pathname === '/api/queue/summary') && request.method() === 'GET') {
    const active = scoped('active')
    const needsMe = active.filter(item => ['needs_input', 'human_review', 'blocked'].includes(item.status))
    await route.fulfill(json({ success: true, counts: counts(), totalCount: items.length, activeCount: active.length, needsLiam: needsMe.length, needsMeItems: needsMe, nextItem: active[0] || null }))
    return
  }
  const detailMatch = requested.pathname.match(/^\/api\/queue\/items\/([^/]+)$/)
  if (detailMatch && request.method() === 'GET') {
    const item = items.find(row => row.id === decodeURIComponent(detailMatch[1]))
    await route.fulfill(json({ success: true, item: item ? { ...item, detail_loaded: true, tags: ['lane:operations'], source_refs: [], receipts: [], run_artifacts: [], pipeline: { nodes: [] } } : null }))
    return
  }
  const closeMatch = requested.pathname.match(/^\/api\/queue\/items\/([^/]+)\/review-close$/)
  if (closeMatch && request.method() === 'POST') {
    closeCalls += 1
    const item = items.find(row => row.id === decodeURIComponent(closeMatch[1]))
    const body = request.postDataJSON()
    assert.equal(item?.id, reviewId)
    assert.equal(body.status, 'done')
    item.status = 'done'
    item.updated_at = '2026-07-18T10:05:00Z'
    await route.fulfill(json({ ok: true, success: true, item_id: reviewId, status: 'done', item }))
    return
  }
  const response = await route.fetch({ url: `${backendUrl}${requested.pathname}${requested.search}` })
  await route.fulfill({ response })
})

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  const scopeControl = page.getByTestId('queue-scope-control')
  await scopeControl.waitFor()
  assert.equal(await scopeControl.getByRole('button', { name: 'Active' }).getAttribute('aria-pressed'), 'true')
  assert.equal(await page.locator('[data-queue-card-id]').count(), 2)

  await page.locator(`[data-queue-card-id="${reviewId}"]`).click()
  const reviewCard = page.locator(`[data-review-card-id="${reviewId}"]`)
  await reviewCard.waitFor()
  assert.match(await reviewCard.locator('header').innerText(), new RegExp(`^${reviewId} — Disposable lifecycle review proof$`))
  assert.equal(await reviewCard.locator('textarea').count(), 1)
  assert.equal(await reviewCard.locator('select').count(), 1)
  assert.equal(await reviewCard.getByRole('button', { name: 'Save/Attach' }).count(), 1)
  assert.deepEqual(await reviewCard.locator('select option').evaluateAll(options => options.map(option => option.value)), ['done', 'needs_input', 'blocked'])

  await page.screenshot({ path: desktopPath, fullPage: true })
  await page.setViewportSize({ width: 760, height: 900 })
  await reviewCard.scrollIntoViewIfNeeded()
  await page.screenshot({ path: narrowPath, fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })

  await reviewCard.locator('textarea').fill('Browser fixture close receipt')
  await Promise.all([
    page.waitForResponse(response => response.url().includes(`/queue/items/${reviewId}/review-close`) && response.status() === 200),
    reviewCard.getByRole('button', { name: 'Save/Attach' }).click(),
  ])
  await reviewCard.waitFor({ state: 'detached' })
  assert.equal(closeCalls, 1)
  assert.equal(await page.locator(`[data-queue-card-id="${reviewId}"]`).count(), 0)
  assert.equal(await page.locator(`[data-queue-card-id="${activeId}"]`).count(), 1)

  await Promise.all([
    page.waitForResponse(response => response.url().includes('/queue/items?scope=history')),
    scopeControl.getByRole('button', { name: 'History' }).click(),
  ])
  await page.locator(`[data-queue-card-id="${reviewId}"]`).waitFor()
  assert.equal(await page.locator('[data-queue-card-id]').count(), 2)

  await page.reload({ waitUntil: 'networkidle' })
  assert.equal(await page.getByTestId('queue-scope-control').getByRole('button', { name: 'History' }).getAttribute('aria-pressed'), 'true')
  await page.locator(`[data-queue-card-id="${reviewId}"]`).waitFor()

  await Promise.all([
    page.waitForResponse(response => response.url().includes('/queue/items?scope=all')),
    page.getByTestId('queue-scope-control').getByRole('button', { name: 'All' }).click(),
  ])
  assert.equal(await page.locator('[data-queue-card-id]').count(), 3)

  await Promise.all([
    page.waitForResponse(response => response.url().includes('/queue/items?scope=active')),
    page.getByTestId('queue-scope-control').getByRole('button', { name: 'Active' }).click(),
  ])
  await page.locator(`[data-queue-card-id="${activeId}"]`).click()
  await page.getByTestId('queue-detail-metadata').waitFor()
  assert.equal(await page.locator(`[data-review-card-id="${activeId}"]`).count(), 0)

  process.stdout.write(`${JSON.stringify({
    success: true,
    default_scope: 'active',
    session_refresh_scope: 'history',
    scope_counts_after_close: { active: scoped('active').length, history: scoped('history').length, all: scoped('all').length },
    review_close_calls: closeCalls,
    closed_item: reviewId,
    unaffected_active_item: activeId,
    non_review_detail: true,
    desktop_screenshot: desktopPath,
    narrow_screenshot: narrowPath,
    live_dashboard_origin: baseUrl,
  }, null, 2)}\n`)
} finally {
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
}
