// One-off manual proof capture (not part of `npm test`): screenshots the real Cockpit
// showing Ask David as the primary interaction and specialists demoted to optional.
import path from 'node:path'
import { chromium } from 'playwright'

const outDir = '/home/liam/agentic-os-live/proofs/ask-david-cockpit-2026-08-07'
const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
page.setDefaultTimeout(20000)
try {
  await page.goto('http://127.0.0.1:3010', { waitUntil: 'networkidle' })
  await page.locator('aside').getByRole('button', { name: 'Cockpit', exact: true }).click()
  await page.getByTestId('ask-david').waitFor()
  await page.screenshot({ path: path.join(outDir, '01-cockpit-ask-david-primary.png'), fullPage: true })

  // Expand the demoted "Consult a specialist" section for a second screenshot.
  await page.getByTestId('specialist-consultations').getByRole('button', { name: /Consult a specialist/ }).click()
  await page.getByTestId('executive-team').waitFor()
  await page.getByTestId('specialist-consultations').scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(outDir, '02-cockpit-specialists-expanded.png'), fullPage: true })

  process.stdout.write('screenshots written\n')
} finally {
  await browser.close()
}
