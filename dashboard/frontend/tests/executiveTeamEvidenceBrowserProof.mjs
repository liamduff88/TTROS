// Revisit: when Executive Team profile/context evidence rendering changes. · Last touched: 2026-08-01.

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const repoRoot = '/home/liam/agentic-os-live'
const proofDir = path.join(repoRoot, 'proofs', 'executive-team-dashboard', '2026-08-01')
const liveEvidence = JSON.parse(fs.readFileSync(path.join(proofDir, 'browser-evidence.json'), 'utf8'))
const recorded = liveEvidence.results.find(result => result.executive_id === 'hermes')
assert.equal(recorded.status, 'success')
const payload = {
  success: true,
  status: 'success',
  request_id: recorded.idempotency.request_id,
  invocation_id: recorded.invocation_id,
  requested_executive: 'Hermes / Executive Coordinator',
  requested_profile: recorded.requested_profile,
  actual_profile: recorded.actual_profile,
  fallback_occurred: recorded.fallback_occurred,
  context: recorded.context,
  queue_effect: recorded.queue_effect,
  response: recorded.response,
  idempotency: { request_id: recorded.idempotency.request_id, replayed: true },
}

const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } })
page.setDefaultTimeout(20000)
let intercepted = 0
try {
  await page.route('**/api/executive-team/consult', async route => {
    intercepted += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
  })
  await page.goto('http://127.0.0.1:3010', { waitUntil: 'domcontentloaded' })
  await page.locator('aside').getByRole('button', { name: 'Cockpit', exact: true }).click()
  await page.locator('[data-executive-card="hermes"]').click()
  const composer = page.getByTestId('executive-composer')
  await composer.locator('textarea').fill('Replay the recorded live consultation evidence for screenshot capture only.')
  await composer.getByRole('button', { name: /^Ask Hermes/ }).click()
  const evidence = page.getByTestId('executive-evidence')
  await evidence.waitFor()
  await evidence.scrollIntoViewIfNeeded()
  const text = await evidence.innerText()
  assert.match(text, /Requested profile:\s*operator-lean/)
  assert.match(text, /Actual profile:\s*operator-lean/)
  assert.match(text, /Fallback:\s*none/)
  assert.match(text, /Context:\s*executive_header_only/)
  assert.match(text, /Executive Header included: yes/)
  assert.match(text, /Full Executive Brief included: no/)
  assert.equal(intercepted, 1)
  const screenshot = path.join(proofDir, '05-safe-profile-context-evidence.png')
  await page.screenshot({ path: screenshot })
  const proof = {
    success: true,
    source: 'recorded live response replayed in browser',
    source_invocation_id: recorded.invocation_id,
    backend_mutated: false,
    model_invoked: false,
    screenshot: path.basename(screenshot),
  }
  fs.writeFileSync(path.join(proofDir, 'profile-context-render-evidence.json'), `${JSON.stringify(proof, null, 2)}\n`)
  process.stdout.write(`${JSON.stringify(proof, null, 2)}\n`)
} finally {
  await browser.close()
}
