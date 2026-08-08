// One-off manual proof capture (not part of `npm test`): drives the real Ask David
// composer with the deterministic-read regression case and screenshots the result.
import path from 'node:path'
import { chromium } from 'playwright'

const outDir = '/home/liam/agentic-os-live/proofs/ask-david-cockpit-2026-08-07'
const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } })
page.setDefaultTimeout(30000)
try {
  await page.goto('http://127.0.0.1:3010', { waitUntil: 'networkidle' })
  await page.locator('aside').getByRole('button', { name: 'Cockpit', exact: true }).click()
  const composer = page.getByTestId('ask-david')
  await composer.waitFor()
  await composer.locator('textarea').fill('where is my pdf branding kit located?')
  await composer.getByRole('button', { name: 'Ask David' }).click()
  await page.getByTestId('ask-david-deterministic').waitFor()
  await composer.scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(outDir, '03-ask-david-deterministic-read-live.png'), fullPage: true })
  process.stdout.write('live composer screenshot written\n')
} finally {
  await browser.close()
}
