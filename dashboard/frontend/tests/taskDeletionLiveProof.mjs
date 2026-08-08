// Revisit: when the authoritative Work Queue deletion proof contract changes. · Last touched: 2026-08-04.
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const repoRoot = path.resolve(import.meta.dirname, '../../..')
const queuePath = path.join(repoRoot, 'queue', 'work_items.jsonl')
const receiptsDir = path.join(repoRoot, 'queue', 'receipts')
const baseUrl = process.env.TASK_DELETION_LIVE_BASE_URL || 'http://127.0.0.1:3011'
const backendUrl = process.env.TASK_DELETION_LIVE_BACKEND_URL || 'http://127.0.0.1:8011'
const screenshotPath = process.env.TASK_DELETION_LIVE_SCREENSHOT
if (!screenshotPath) throw new Error('TASK_DELETION_LIVE_SCREENSHOT is required')

const proofPrefix = `Task deletion proof ${Date.now()}`
const contextSentinel = `FORBIDDEN_LIVE_CONTEXT_${crypto.randomUUID().replaceAll('-', '')}`
const fixtureIds = new Set()
const operations = []
let mainDeleteBody = null

const parseQueue = () => fs.readFileSync(queuePath, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line))
const executorCount = () => {
  let count = 0
  for (const entry of fs.readdirSync('/proc')) {
    if (!/^\d+$/.test(entry)) continue
    try {
      const args = fs.readFileSync(`/proc/${entry}/cmdline`).toString('utf8').split('\0').filter(Boolean)
      const cwd = fs.realpathSync(`/proc/${entry}/cwd`)
      if (cwd === repoRoot && args.some(value => value.endsWith('/tools/aos-orchestration-runner.py')) && args.includes('--execute-item')) count += 1
    } catch {
      // Processes may exit while /proc is read.
    }
  }
  return count
}
const metrics = () => {
  const bytes = fs.readFileSync(queuePath)
  const items = parseQueue()
  const counts = Object.fromEntries(['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled'].map(status => [status, items.filter(item => item.status === status).length]))
  return {
    queue_count: items.length,
    queue_sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    status_counts: counts,
    tombstone_count: fs.readdirSync(receiptsDir).filter(name => /^task-deletion-.*\.json$/.test(name)).length,
    active_claim_count: items.filter(item => item?.claim?.claimed_by).length,
    detached_executor_count: executorCount(),
  }
}
const record = (operation, before, after, result) => operations.push({ operation, before, after, result })

async function api(pathname, options = {}) {
  const response = await fetch(`${backendUrl}${pathname}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const body = await response.json().catch(() => ({}))
  return { status: response.status, body }
}
async function createFixture(title, extra = {}) {
  const response = await api('/api/queue/items', {
    method: 'POST',
    body: JSON.stringify({
      title: `${proofPrefix} — ${title}`,
      owner: 'operations',
      priority: 'urgent',
      tags: 'task_deletion_proof',
      source: 'dashboard/task-deletion-proof',
      context: contextSentinel,
      definition_of_done: 'Safe local fixture only.',
      ...extra,
    }),
  })
  assert.equal(response.status, 200, JSON.stringify(response.body))
  fixtureIds.add(response.body.item.id)
  return response.body.item
}
async function detail(itemId) {
  const response = await api(`/api/queue/items/${encodeURIComponent(itemId)}`)
  return response.status === 200 ? response.body.item : null
}
async function setStatus(itemId, status) {
  const response = await api(`/api/queue/items/${encodeURIComponent(itemId)}/status`, { method: 'POST', body: JSON.stringify({ status }) })
  assert.equal(response.status, 200, JSON.stringify(response.body))
  return response.body
}
async function directDelete(itemId, reason, requestId = `delete-proof-${crypto.randomUUID().replaceAll('-', '')}`) {
  const item = await detail(itemId)
  if (!item) return null
  return api(`/api/queue/items/${encodeURIComponent(itemId)}`, {
    method: 'DELETE',
    body: JSON.stringify({ expected_record_hash: item.record_hash, deletion_reason: reason, request_id: requestId }),
  })
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } })
await page.addInitScript(() => {
  sessionStorage.setItem('aos.dashboard.queue-scope.v1', 'all')
  sessionStorage.setItem('aos.dashboard.shell.v1', JSON.stringify({
    view: 'work-queue', viewParams: {},
    sessionTabs: [
      { id: 'cockpit', label: 'Cockpit', workbench: 'hermes', preview: false },
      { id: 'work-queue', label: 'Work Queue', workbench: 'codex', preview: true, params: {} },
    ],
  }))
})
await page.route('**/api/**', async route => {
  const request = route.request()
  if (request.method() === 'DELETE' && /\/api\/queue\/items\//.test(request.url())) mainDeleteBody ||= request.postDataJSON()
  const url = new URL(request.url())
  if (!url.pathname.startsWith('/api/queue/')) {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, counts: {}, queue_items: [], needs_me: [] }) })
    return
  }
  const forwarded = await route.fetch({ url: `${backendUrl}${url.pathname}${url.search}` })
  await route.fulfill({ response: forwarded })
})

async function refreshQueue() {
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await page.waitForTimeout(250)
}
async function selectItem(itemId) {
  await refreshQueue()
  const card = page.locator(`[data-queue-card-id="${itemId}"]`)
  await card.waitFor()
  await card.click()
  await page.getByTestId('task-deletion-control').waitFor()
}
async function openDelete(itemId, reason = 'Safe fixture cleanup') {
  await selectItem(itemId)
  await page.getByTestId('open-task-deletion').click()
  const dialog = page.getByTestId('task-deletion-dialog')
  await dialog.waitFor()
  assert.equal(await page.getByTestId('task-deletion-item-id').innerText(), itemId)
  await dialog.getByTestId('task-deletion-reason').fill(reason)
  await dialog.getByTestId('task-deletion-confirmation').fill(itemId)
  return dialog
}
async function uiDelete(itemId, reason = 'Safe fixture cleanup') {
  const dialog = await openDelete(itemId, reason)
  if (reason === 'Primary safe fixture cleanup') await dialog.screenshot({ path: screenshotPath })
  const responsePromise = page.waitForResponse(response => response.request().method() === 'DELETE' && response.url().includes(`/queue/items/${itemId}`))
  await dialog.getByTestId('confirm-task-deletion').click()
  const response = await responsePromise
  const body = await response.json()
  return { status: response.status(), body }
}
async function uiRefusal(itemId, expectedCode, expectedText) {
  const before = metrics()
  const itemBefore = await detail(itemId)
  const response = await uiDelete(itemId, `Refusal proof ${expectedCode}`)
  const after = metrics()
  const itemAfter = await detail(itemId)
  assert.notEqual(response.status, 200)
  assert.equal(response.body.detail.code, expectedCode)
  assert.match(await page.getByTestId('task-deletion-notice').innerText(), expectedText)
  assert.equal(after.tombstone_count, before.tombstone_count)
  assert.equal(itemAfter?.record_hash, itemBefore?.record_hash)
  record(`refuse_${expectedCode}`, before, after, { status: response.status, code: expectedCode, blockers: response.body.detail.blockers || {} })
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  return response
}

const startMetrics = metrics()
try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })

  // Create the primary fixture through the rendered dashboard form.
  const createBefore = metrics()
  if (!await page.getByText('Advanced / manual create', { exact: true }).isVisible()) {
    if (!await page.getByRole('button', { name: 'Expand work items', exact: true }).isVisible().catch(() => false)) {
      const listed = await api('/api/queue/items?scope=all')
      const safeSelection = listed.body.items.find(item => item.status !== 'human_review')
      assert.ok(safeSelection?.id, 'a non-review item is required to expose the existing expand control')
      await page.locator(`[data-queue-card-id="${safeSelection.id}"]`).click()
    }
    await page.getByRole('button', { name: 'Expand work items', exact: true }).click()
  }
  await page.getByText('Advanced / manual create', { exact: true }).click()
  const createForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'Create', exact: true }) })
  await createForm.getByLabel('Title required').fill(`${proofPrefix} — primary UI fixture`)
  await createForm.getByLabel('Owner').selectOption('operations')
  await createForm.getByLabel('Priority').selectOption('urgent')
  await createForm.getByLabel('Tags').fill('task_deletion_proof')
  await createForm.getByLabel('Source', { exact: true }).fill('dashboard/task-deletion-proof')
  await createForm.getByLabel('Context', { exact: true }).fill(contextSentinel)
  const createdResponse = page.waitForResponse(response => response.url().endsWith('/api/queue/items') && response.request().method() === 'POST')
  await createForm.getByRole('button', { name: 'Create', exact: true }).click()
  const primaryCreate = await (await createdResponse).json()
  const primaryId = primaryCreate.item.id
  fixtureIds.add(primaryId)
  const createAfter = metrics()
  assert.ok(await detail(primaryId))
  record('create_primary_fixture', createBefore, createAfter, { item_id: primaryId })

  const cancelBefore = metrics()
  const cancelItemBefore = await detail(primaryId)
  const cancelDialog = await openDelete(primaryId, 'Cancelled confirmation proof')
  await cancelDialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  const cancelAfter = metrics()
  const cancelItemAfter = await detail(primaryId)
  assert.equal(cancelAfter.tombstone_count, cancelBefore.tombstone_count)
  assert.equal(cancelItemAfter?.record_hash, cancelItemBefore?.record_hash)
  record('cancel_confirmation', cancelBefore, cancelAfter, { item_id: primaryId, delete_request_sent: false })

  const deleteBefore = metrics()
  const primaryDelete = await uiDelete(primaryId, 'Primary safe fixture cleanup')
  const deleteAfter = metrics()
  assert.equal(primaryDelete.status, 200, JSON.stringify(primaryDelete.body))
  assert.equal(deleteAfter.tombstone_count, deleteBefore.tombstone_count + 1)
  assert.equal(await detail(primaryId), null)
  assert.equal(await page.locator(`[data-queue-card-id="${primaryId}"]`).count(), 0)
  assert.notEqual(await page.locator('[data-queue-card-id][aria-pressed="true"]').getAttribute('data-queue-card-id'), primaryId)
  assert.notEqual(await page.evaluate(() => performance.getEntriesByType('navigation')[0]?.type), 'reload')
  record('delete_primary_fixture', deleteBefore, deleteAfter, {
    item_id: primaryId,
    tombstone_reference: primaryDelete.body.tombstone_reference,
    selected_next_without_reload: true,
  })

  const tombstonePath = path.join(repoRoot, primaryDelete.body.tombstone_reference)
  const tombstoneText = fs.readFileSync(tombstonePath, 'utf8')
  const tombstone = JSON.parse(tombstoneText)
  const allowedKeys = ['created_at', 'deleted_at', 'deleted_by', 'deletion_reason', 'item_id', 'owner', 'previous_status', 'record_sha256', 'title', 'workbench']
  assert.ok(Object.keys(tombstone).every(key => allowedKeys.includes(key)))
  assert.ok(!tombstoneText.includes(contextSentinel))
  for (const forbidden of ['context', 'prompt', 'definition_of_done', 'sources', 'brain_context_used', 'model_output', 'receipts', 'artifacts', 'token_usage', 'credentials']) {
    assert.ok(!(forbidden in tombstone))
  }

  const replayBefore = metrics()
  const replay = await page.evaluate(async ({ itemId, body }) => {
    const response = await fetch(`/api/queue/items/${itemId}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    return { status: response.status, body: await response.json() }
  }, { itemId: primaryId, body: mainDeleteBody })
  const replayAfter = metrics()
  assert.equal(replay.status, 200)
  assert.equal(replay.body.idempotency.replayed, true)
  assert.equal(replayAfter.tombstone_count, replayBefore.tombstone_count)
  assert.equal(await detail(primaryId), null)
  record('idempotent_replay', replayBefore, replayAfter, { item_id: primaryId, replayed: true })

  const independent = await page.evaluate(async ({ itemId, body }) => {
    const response = await fetch(`/api/queue/items/${itemId}`, {
      method: 'DELETE', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, request_id: `delete-independent-${crypto.randomUUID().replaceAll('-', '')}` }),
    })
    return { status: response.status, body: await response.json() }
  }, { itemId: primaryId, body: mainDeleteBody })
  assert.equal(independent.status, 410)
  assert.equal(independent.body.detail.code, 'already_deleted')

  const stale = await createFixture('stale fixture')
  const staleDialog = await openDelete(stale.id, 'Stale fixture cleanup')
  await setStatus(stale.id, 'blocked')
  const staleBefore = metrics()
  const staleItemBefore = await detail(stale.id)
  const staleResponsePromise = page.waitForResponse(response => response.request().method() === 'DELETE' && response.url().includes(`/queue/items/${stale.id}`))
  await staleDialog.getByTestId('confirm-task-deletion').click()
  const staleResponse = await staleResponsePromise
  const staleBody = await staleResponse.json()
  const staleAfter = metrics()
  const staleItemAfter = await detail(stale.id)
  assert.equal(staleResponse.status(), 409)
  assert.equal(staleBody.detail.code, 'stale_queue_state')
  assert.equal(staleAfter.tombstone_count, staleBefore.tombstone_count)
  assert.equal(staleItemAfter?.record_hash, staleItemBefore?.record_hash)
  record('refuse_stale_state', staleBefore, staleAfter, { item_id: stale.id, code: staleBody.detail.code })
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  const staleCleanupBefore = metrics()
  const staleCleanup = await uiDelete(stale.id)
  const staleCleanupAfter = metrics()
  assert.equal(staleCleanup.status, 200)
  record('cleanup_stale_fixture', staleCleanupBefore, staleCleanupAfter, { item_id: stale.id })

  const running = await createFixture('running fixture')
  await setStatus(running.id, 'agent_working')
  await uiRefusal(running.id, 'agent_working', /cancel or stop it first/i)
  await setStatus(running.id, 'cancelled')
  const runningCleanupBefore = metrics()
  const runningCleanup = await uiDelete(running.id)
  const runningCleanupAfter = metrics()
  assert.equal(runningCleanup.status, 200)
  record('cleanup_running_fixture_after_cancel', runningCleanupBefore, runningCleanupAfter, { item_id: running.id })

  const target = await createFixture('dependency target')
  const dependent = await createFixture('dependent fixture', { depends_on: target.id })
  const dependencyRefusal = await uiRefusal(target.id, 'active_dependents', new RegExp(dependent.id))
  assert.deepEqual(dependencyRefusal.body.detail.blockers.dependent_ids, [dependent.id])
  const dependentCleanupBefore = metrics()
  const dependentCleanup = await uiDelete(dependent.id)
  const dependentCleanupAfter = metrics()
  assert.equal(dependentCleanup.status, 200)
  record('cleanup_dependent_fixture', dependentCleanupBefore, dependentCleanupAfter, { item_id: dependent.id })
  const targetCleanupBefore = metrics()
  const targetCleanup = await uiDelete(target.id)
  const targetCleanupAfter = metrics()
  assert.equal(targetCleanup.status, 200)
  record('cleanup_dependency_target', targetCleanupBefore, targetCleanupAfter, { item_id: target.id })

  const protectedId = 'AOS-2026-0071'
  const protectedBefore = metrics()
  const protectedItem = await detail(protectedId)
  let protectedResponse
  if (protectedItem) {
    protectedResponse = await uiDelete(protectedId, 'Protected item refusal proof')
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  } else {
    protectedResponse = await api(`/api/queue/items/${protectedId}`, {
      method: 'DELETE',
      body: JSON.stringify({ expected_record_hash: '0'.repeat(64), deletion_reason: 'Protected item refusal proof', request_id: `delete-protected-${crypto.randomUUID().replaceAll('-', '')}` }),
    })
  }
  const protectedAfter = metrics()
  const protectedItemAfter = await detail(protectedId)
  assert.equal(protectedResponse.status, 403)
  assert.equal(protectedResponse.body.detail.code, 'immutable_item')
  assert.equal(protectedAfter.tombstone_count, protectedBefore.tombstone_count)
  if (protectedItem) assert.equal(protectedItemAfter?.record_hash, protectedItem.record_hash)
  record('refuse_protected_item', protectedBefore, protectedAfter, { item_id: protectedId, code: 'immutable_item' })

  const endMetrics = metrics()
  const remainingFixtureIds = parseQueue().filter(item => fixtureIds.has(item.id)).map(item => item.id)
  assert.deepEqual(remainingFixtureIds, [])

  process.stdout.write(`${JSON.stringify({
    success: true,
    start: startMetrics,
    end: endMetrics,
    operations,
    primary_tombstone: {
      reference: primaryDelete.body.tombstone_reference,
      keys: Object.keys(tombstone).sort(),
      record_sha256: tombstone.record_sha256,
      bounded_title_length: tombstone.title.length,
      bounded_reason_length: tombstone.deletion_reason.length,
      forbidden_context_absent: !tombstoneText.includes(contextSentinel),
    },
    fixture_count_cleaned: fixtureIds.size,
    fixture_queue_delta: 0,
    concurrent_global_queue_delta: endMetrics.queue_count - startMetrics.queue_count,
    protected_id_unchanged: true,
    screenshot: screenshotPath,
  }, null, 2)}\n`)
} finally {
  // Best-effort cleanup uses only the new deletion route and dependency-safe order.
  const queued = parseQueue().filter(item => fixtureIds.has(item.id))
  const byDependency = [...queued].sort((left, right) => Number(Boolean(right.depends_on?.length)) - Number(Boolean(left.depends_on?.length)))
  for (const item of byDependency) {
    try {
      if (item.status === 'agent_working' || item?.claim?.claimed_by) await setStatus(item.id, 'cancelled')
      await directDelete(item.id, 'Best-effort proof cleanup')
    } catch {
      // The final report will fail its remaining-fixture assertion when cleanup is incomplete.
    }
  }
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
}
