import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseUrl = process.env.REVIEW_CARD_BASE_URL || 'http://127.0.0.1:3010'
const backendUrl = process.env.REVIEW_CARD_BACKEND_URL || 'http://127.0.0.1:8010'
const desktopPath = process.env.REVIEW_CARD_DESKTOP_SCREENSHOT
const narrowPath = process.env.REVIEW_CARD_NARROW_SCREENSHOT
const keepId = process.env.REVIEW_CARD_KEEP_ID
const closeId = process.env.REVIEW_CARD_CLOSE_ID
const failId = process.env.REVIEW_CARD_FAIL_ID

for (const [name, value] of Object.entries({ desktopPath, narrowPath, keepId, closeId, failId })) {
  if (!value) throw new Error(`Missing browser-proof input: ${name}`)
}

const excluded = [
  'summary_for_operator', 'prompt', 'context', 'Run section', 'Artifacts',
  'receipt path', 'filesystem path', 'worker transcript', 'test output',
  'owner', 'lane', 'priority', 'tags', 'timestamps', 'tokens', 'claims',
  'dependencies',
]

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const closeCalls = new Map()
await page.route('**/api/**', async route => {
  const requested = new URL(route.request().url())
  const response = await route.fetch({ url: `${backendUrl}${requested.pathname}${requested.search}` })
  await route.fulfill({ response })
})
page.on('request', request => {
  if (request.method() !== 'POST' || !request.url().includes('/review-close')) return
  const itemId = decodeURIComponent(request.url().split('/queue/items/')[1].split('/review-close')[0])
  closeCalls.set(itemId, (closeCalls.get(itemId) || 0) + 1)
})

try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  const expectedIds = [keepId, closeId, failId]
  for (const itemId of expectedIds) await page.locator(`[data-review-card-id="${itemId}"]`).waitFor()

  const cards = page.locator('[data-review-card-id]')
  assert.equal(await cards.count(), expectedIds.length)
  for (const itemId of expectedIds) {
    const card = page.locator(`[data-review-card-id="${itemId}"]`)
    assert.match(await card.locator('header').innerText(), new RegExp(`^${itemId} — .+`))
    assert.equal(await card.locator('textarea').count(), 1)
    assert.equal(await card.locator('select').count(), 1)
    assert.equal(await card.getByRole('button', { name: 'Save/Attach' }).count(), 1)
    assert.deepEqual(await card.locator('select option').evaluateAll(options => options.map(option => option.value)), ['done', 'needs_input', 'blocked'])
    const text = (await card.innerText()).toLowerCase()
    for (const term of excluded) assert.equal(text.includes(term.toLowerCase()), false, `${itemId}: ${term}`)
    assert.equal(await card.locator('details').count(), 0)
  }

  const keepCard = page.locator(`[data-review-card-id="${keepId}"]`)
  const keepReceipt = keepCard.locator('textarea')
  await keepReceipt.focus()
  assert.equal(await keepReceipt.evaluate(element => element === document.activeElement), true)
  await page.keyboard.press('Tab')
  assert.equal(await keepCard.locator('select').evaluate(element => element === document.activeElement), true)
  await page.keyboard.press('Tab')
  assert.equal(await keepCard.getByRole('button', { name: 'Save/Attach' }).evaluate(element => element === document.activeElement), true)

  await page.screenshot({ path: desktopPath, fullPage: true })

  await keepReceipt.fill('Keep-status receipt survives refresh')
  await keepCard.locator('select').selectOption('blocked')
  await Promise.all([
    page.waitForResponse(response => response.url().includes(`/queue/items/${keepId}/review-close`) && response.status() === 200),
    keepCard.getByRole('button', { name: 'Save/Attach' }).click(),
  ])
  await page.reload({ waitUntil: 'networkidle' })
  const persistedCard = page.locator(`[data-review-card-id="${keepId}"]`)
  await persistedCard.waitFor()
  assert.equal(await persistedCard.locator('textarea').inputValue(), 'Keep-status receipt survives refresh')
  assert.equal(await persistedCard.locator('select').inputValue(), 'blocked')
  assert.equal(await persistedCard.getByRole('button', { name: 'Save/Attach' }).isDisabled(), true)

  const unaffectedCard = page.locator(`[data-review-card-id="${closeId}"]`)
  assert.equal(await unaffectedCard.locator('textarea').inputValue(), '')
  assert.equal(await unaffectedCard.locator('select').inputValue(), 'done')

  const failCard = page.locator(`[data-review-card-id="${failId}"]`)
  await failCard.locator('textarea').fill('Failure receipt must remain typed')
  await failCard.locator('select').selectOption('needs_input')
  await Promise.all([
    page.waitForResponse(response => response.url().includes(`/queue/items/${failId}/review-close`) && response.status() === 400),
    failCard.getByRole('button', { name: 'Save/Attach' }).click(),
  ])
  assert.equal(await failCard.locator('textarea').inputValue(), 'Failure receipt must remain typed')
  assert.equal(await failCard.locator('select').inputValue(), 'needs_input')
  await failCard.getByRole('alert').waitFor()

  await unaffectedCard.locator('textarea').fill('Successful close removes this card')
  await unaffectedCard.locator('select').selectOption('done')
  await Promise.all([
    page.waitForResponse(response => response.url().includes(`/queue/items/${closeId}/review-close`) && response.status() === 200),
    unaffectedCard.getByRole('button', { name: 'Save/Attach' }).click(),
  ])
  await page.locator(`[data-review-card-id="${closeId}"]`).waitFor({ state: 'detached' })
  assert.equal(await page.locator(`[data-review-card-id="${keepId}"]`).count(), 1)
  assert.equal(await page.locator(`[data-review-card-id="${failId}"]`).count(), 1)

  await failCard.getByRole('alert').waitFor({ state: 'detached', timeout: 7000 })
  await page.setViewportSize({ width: 760, height: 900 })
  await page.screenshot({ path: narrowPath, fullPage: true })

  assert.equal(closeCalls.get(keepId), 1)
  assert.equal(closeCalls.get(closeId), 1)
  assert.equal(closeCalls.get(failId), 1)
  process.stdout.write(`${JSON.stringify({
    success: true,
    initial_card_count: expectedIds.length,
    close_calls: Object.fromEntries(closeCalls),
    persisted: { item_id: keepId, receipt: 'Keep-status receipt survives refresh', status: 'blocked' },
    removed_item_id: closeId,
    unaffected_item_id: closeId,
    failure_preserved_item_id: failId,
    keyboard_order: ['textarea', 'select', 'Save/Attach'],
    excluded_clutter: excluded,
    desktop_screenshot: desktopPath,
    narrow_screenshot: narrowPath,
  }, null, 2)}\n`)
} finally {
  await browser.close()
}
