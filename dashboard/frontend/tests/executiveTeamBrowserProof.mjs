// Revisit: when the Executive Team Cockpit browser contract changes. · Last touched: 2026-08-01.

import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const repoRoot = '/home/liam/agentic-os-live'
const proofDir = path.join(repoRoot, 'proofs', 'executive-team-dashboard', '2026-08-01')
const baseUrl = process.env.EXECUTIVE_TEAM_BASE_URL || 'http://127.0.0.1:3010'
const queuePath = path.join(repoRoot, 'queue', 'work_items.jsonl')
const runLedgerPath = path.join(repoRoot, 'queue', 'run_ledger.jsonl')
const tokenLedgerPath = path.join(repoRoot, 'queue', 'token_ledger.jsonl')
const receiptDir = path.join(repoRoot, 'queue', 'receipts')
const prompts = [
  ['hermes', 'operator-lean', 'What should I focus on today for Time to Revenue? Give me your judgment and the three most important actions. Do not create work or take external action.'],
  ['revenue', 'aos-revenue', 'Identify the strongest immediate route to new revenue for Time to Revenue. Give me three actions and explain why. Do not send or publish anything.'],
  ['marketing', 'aos-marketing', 'Propose one focused marketing campaign supporting the current revenue priority. Give the audience, core message, asset and next step. Do not publish anything.'],
  ['delivery', 'aos-delivery', 'Outline the first five steps for onboarding a new Speed-to-Lead client. Flag the information you would need. Do not take external action.'],
  ['operations', 'aos-ops', 'Identify the top three operational priorities or blockers that could slow Time to Revenue this week. Recommend the next action for each.'],
  ['executive-team', 'aos-orchestrator', 'Coordinate Revenue and Marketing around the Speed-to-Lead offer. Return one integrated plan with owners, sequencing and the decision Liam needs to make. Do not execute anything.'],
]

const sha256 = value => crypto.createHash('sha256').update(value).digest('hex')
const nonEmptyLines = file => fs.readFileSync(file, 'utf8').split('\n').filter(line => line.trim()).length
const snapshot = () => ({
  queue_count: nonEmptyLines(queuePath),
  queue_sha256: sha256(fs.readFileSync(queuePath)),
  run_ledger_count: nonEmptyLines(runLedgerPath),
  token_ledger_count: nonEmptyLines(tokenLedgerPath),
  receipt_count: fs.readdirSync(receiptDir).filter(name => name !== '.gitkeep' && fs.statSync(path.join(receiptDir, name)).isFile()).length,
})

fs.mkdirSync(proofDir, { recursive: true })
const before = snapshot()
const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } })
page.setDefaultTimeout(150000)
const consoleErrors = []
const failedResponses = []
const consultationRequests = []
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('response', response => {
  if (response.status() >= 400) failedResponses.push({ url: response.url(), status: response.status() })
})
page.on('request', request => {
  if (request.method() === 'POST' && request.url().includes('/api/executive-team/consult')) consultationRequests.push(request.postDataJSON())
})

const results = []
try {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
  await page.locator('aside').getByRole('button', { name: 'Cockpit', exact: true }).click()
  await page.getByTestId('executive-team').waitFor()
  assert.equal(await page.locator('[data-executive-card]').count(), 6)
  for (const [id, profile] of prompts) {
    const card = page.locator(`[data-executive-card="${id}"]`)
    assert.equal(await card.getAttribute('data-profile'), profile)
  }
  await page.screenshot({ path: path.join(proofDir, '01-cockpit-executive-team-cards.png'), fullPage: true })

  for (const [id, profile, prompt] of prompts) {
    await page.locator(`[data-executive-card="${id}"]`).click()
    const composer = page.getByTestId('executive-composer')
    await composer.locator('textarea').fill(prompt)
    const responsePromise = page.waitForResponse(response => response.url().includes('/api/executive-team/consult') && response.request().method() === 'POST')
    const submit = composer.getByRole('button', { name: new RegExp(`^Ask `) })
    if (id === 'hermes') await submit.evaluate(button => { button.click(); button.click() })
    else await submit.click()
    const httpResponse = await responsePromise
    const payload = await httpResponse.json()
    await page.getByTestId(payload.success ? 'executive-success' : 'executive-failure').waitFor()
    assert.equal(payload.requested_profile, profile)
    assert.equal(payload.fallback_occurred, false)
    assert.equal(payload.queue_effect?.items_created || 0, 0)
    if (payload.actual_profile) assert.equal(payload.actual_profile, profile)
    results.push({
      executive_id: id,
      requested_profile: profile,
      actual_profile: payload.actual_profile,
      fallback_occurred: payload.fallback_occurred,
      status: payload.status,
      context: payload.context,
      queue_effect: payload.queue_effect,
      idempotency: payload.idempotency,
      invocation_id: payload.invocation_id,
      response: String(payload.response || '').slice(0, 6000),
      error: payload.error || null,
    })
    if (payload.success && id !== 'hermes' && !fs.existsSync(path.join(proofDir, '02-department-response.png'))) {
      await page.screenshot({ path: path.join(proofDir, '02-department-response.png'), fullPage: true })
    }
    if (id === 'executive-team') await page.screenshot({ path: path.join(proofDir, '03-executive-team-response.png'), fullPage: true })
    if (!payload.success && !fs.existsSync(path.join(proofDir, '04-honest-profile-failure.png'))) {
      await page.screenshot({ path: path.join(proofDir, '04-honest-profile-failure.png'), fullPage: true })
      const retryResponse = page.waitForResponse(response => response.url().includes('/api/executive-team/consult') && response.request().method() === 'POST')
      await composer.getByRole('button', { name: 'Retry safely' }).click()
      const replay = await (await retryResponse).json()
      assert.equal(replay.idempotency?.replayed, true)
      assert.equal(replay.request_id, payload.request_id)
      results.at(-1).safe_retry = replay.idempotency
    }
  }

  assert.equal(consultationRequests.filter(request => request.executive_id === 'hermes').length, 1)
  const after = snapshot()
  assert.equal(after.queue_count, before.queue_count)
  assert.equal(after.queue_sha256, before.queue_sha256)
  const operator = results.find(result => result.executive_id === 'hermes')
  const orchestrator = results.find(result => result.executive_id === 'executive-team')
  assert.equal(operator.context?.classification, 'executive_header_only')
  assert.equal(operator.context?.executive_header_included, true)
  assert.equal(operator.context?.executive_brief_included, false)
  assert.equal(orchestrator.context?.classification, 'full_executive_brief')
  assert.equal(orchestrator.context?.executive_brief_included, true)
  assert.equal(orchestrator.context?.executive_header_included, false)

  const evidence = {
    success: results.every(result => result.status === 'success'),
    timestamp: new Date().toISOString(),
    base_url: baseUrl,
    permanent_card_count: 6,
    before,
    after,
    queue_unchanged: before.queue_count === after.queue_count && before.queue_sha256 === after.queue_sha256,
    double_click_request_count: consultationRequests.filter(request => request.executive_id === 'hermes').length,
    results,
    console_errors: consoleErrors,
    failed_responses: failedResponses,
    screenshots: fs.readdirSync(proofDir).filter(name => name.endsWith('.png')).sort(),
  }
  fs.writeFileSync(path.join(proofDir, 'browser-evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
  process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`)
} finally {
  await browser.close()
}
