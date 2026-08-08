// Revisit: when Executive Team transport-failure rendering changes. · Last touched: 2026-08-01.

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const repoRoot = '/home/liam/agentic-os-live'
const proofDir = path.join(repoRoot, 'proofs', 'executive-team-dashboard', '2026-08-01')
const screenshot = path.join(proofDir, '04-honest-backend-failure.png')
const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } })
page.setDefaultTimeout(20000)
let intercepted = 0
const requestIds = []
try {
  await page.route('**/api/executive-team/consult', async route => {
    intercepted += 1
    requestIds.push(route.request().postDataJSON().request_id)
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Deterministic proof: backend unavailable.' }),
    })
  })
  await page.goto('http://127.0.0.1:3010', { waitUntil: 'domcontentloaded' })
  await page.locator('aside').getByRole('button', { name: 'Cockpit', exact: true }).click()
  await page.locator('[data-executive-card="revenue"]').click()
  const composer = page.getByTestId('executive-composer')
  await composer.locator('textarea').fill('Deterministic transport failure rendering proof. Do not execute anything.')
  await composer.getByRole('button', { name: /^Ask Revenue$/ }).click()
  const failure = page.getByTestId('executive-failure')
  await failure.waitFor()
  assert.match(await failure.innerText(), /Deterministic proof: backend unavailable\./)
  const retryResponse = page.waitForResponse(response => response.url().includes('/api/executive-team/consult') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Retry safely' }).click()
  await retryResponse
  await failure.waitFor()
  assert.equal(intercepted, 2)
  assert.equal(requestIds[0], requestIds[1])
  await page.screenshot({ path: screenshot, fullPage: true })
  const evidence = {
    success: true,
    deterministic_browser_intercept: true,
    intercepted_status: 503,
    backend_mutated: false,
    model_invoked: false,
    queue_action: 'none',
    retry_same_request_id: true,
    rendered_message: 'Deterministic proof: backend unavailable.',
    screenshot: path.basename(screenshot),
  }
  fs.writeFileSync(path.join(proofDir, 'failure-evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
  process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`)
} finally {
  await browser.close()
}
