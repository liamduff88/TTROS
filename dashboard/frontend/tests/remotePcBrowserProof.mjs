// Revisit: when the Remote PC view or its Tailscale/Cloudflare access paths change. · Last touched: 2026-10-26.
// Drives the real Dashboard through Tailscale Serve (so the identity header is
// added by Tailscale, not forged), runs one confirmed PowerShell command on the
// Windows host, and checks desktop + phone layouts. Also proves a connection
// without identity sees the locked state.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { chromium } from 'playwright'

const tailnetUrl = process.env.REMOTE_PC_TAILNET_URL || 'https://vrs-global.tailb38520.ts.net'
const localUrl = process.env.REMOTE_PC_LOCAL_URL || 'http://127.0.0.1:3010'
const outDir = process.env.REMOTE_PC_PROOF_DIR || fs.mkdtempSync(path.join(os.tmpdir(), 'remote-pc-proof-'))
fs.mkdirSync(outDir, { recursive: true })
const shot = (page, name) => page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: false })
const results = []
const record = (label, value) => { results.push(`${label}: ${value}`); console.log(`${label}: ${value}`) }

const noHorizontalOverflow = page => page.evaluate(() => {
  const main = document.getElementById('aos-main-scroll')
  return {
    document: document.documentElement.scrollWidth <= window.innerWidth,
    main: main ? main.scrollWidth <= main.clientWidth : false,
  }
})

const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
})

try {
  for (const viewport of [{ name: 'desktop', width: 1440, height: 900 }, { name: 'phone', width: 393, height: 852 }]) {
    const context = await browser.newContext({ viewport, deviceScaleFactor: viewport.name === 'phone' ? 3 : 1, isMobile: viewport.name === 'phone', hasTouch: viewport.name === 'phone' })
    const page = await context.newPage()
    await page.goto(`${tailnetUrl}/remote-pc`, { waitUntil: 'networkidle' })
    await page.getByTestId('remote-pc-status').waitFor({ timeout: 45000 })
    const statusText = await page.getByTestId('remote-pc-status').innerText()
    assert.match(statusText, /VRS-GLOBAL/)
    assert.match(statusText, /liamduff88@gmail\.com/)
    record(`${viewport.name} status`, statusText.replace(/\s+/g, ' '))
    const navCount = await page.locator(viewport.name === 'phone' ? '[data-testid="mobile-nav"] [data-nav-destination]' : '[data-testid="sidebar"] [data-nav-destination]').count()
    record(`${viewport.name} nav destinations`, navCount)
    assert.equal(navCount, 6)
    await shot(page, `${viewport.name}-01-status`)

    const command = `Write-Output "remote-pc proof ${viewport.name}"; (Get-CimInstance Win32_OperatingSystem).Caption; $env:COMPUTERNAME`
    await page.getByTestId('remote-pc-command').fill(command)
    await page.getByTestId('remote-pc-run').click()
    await page.getByTestId('remote-pc-confirm').waitFor()
    assert.equal(await page.getByTestId('remote-pc-confirm-command').innerText(), command)
    await shot(page, `${viewport.name}-02-confirm`)
    await page.getByTestId('remote-pc-confirm-run').click()
    await page.getByTestId('remote-pc-result').waitFor({ timeout: 90000 })
    const exit = await page.getByTestId('remote-pc-exit-code').innerText()
    const stdout = await page.getByTestId('remote-pc-stdout').innerText()
    record(`${viewport.name} run`, `${exit} | ${stdout.replace(/\s+/g, ' ')}`)
    assert.equal(exit, 'exit 0')
    assert.match(stdout, new RegExp(`remote-pc proof ${viewport.name}`))
    assert.match(stdout, /Windows 11 Home/)
    await shot(page, `${viewport.name}-03-result`)
    const overflowRun = await noHorizontalOverflow(page)
    record(`${viewport.name} overflow after run`, JSON.stringify(overflowRun))
    assert.deepEqual(overflowRun, { document: true, main: true })

    await page.locator('[data-hub-tab="files"]').click()
    await page.getByTestId('remote-pc-listing').locator('button, span').first().waitFor({ timeout: 30000 })
    await shot(page, `${viewport.name}-04-files`)
    const overflowFiles = await noHorizontalOverflow(page)
    record(`${viewport.name} overflow files`, JSON.stringify(overflowFiles))
    assert.deepEqual(overflowFiles, { document: true, main: true })

    await page.locator('[data-hub-tab="desktop"]').click()
    await page.getByTestId('remote-pc-desktop').waitFor()
    record(`${viewport.name} desktop`, (await page.getByTestId('remote-pc-desktop').innerText()).split('\n').slice(0, 2).join(' | '))
    await shot(page, `${viewport.name}-05-desktop`)

    await page.locator('[data-hub-tab="receipts"]').click()
    await page.getByTestId('remote-pc-receipt-row').first().waitFor()
    await shot(page, `${viewport.name}-06-receipts`)
    await context.close()
  }

  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await context.newPage()
  await page.goto(`${localUrl}/remote-pc`, { waitUntil: 'networkidle' })
  await page.getByText('Remote PC is locked on this connection').waitFor({ timeout: 30000 })
  assert.equal(await page.getByTestId('remote-pc-command').count(), 0)
  record('local without identity', 'locked, no command box')
  await shot(page, 'local-locked')
  await context.close()
} finally {
  await browser.close()
}

fs.writeFileSync(path.join(outDir, 'remote-pc-browser-proof.txt'), `${results.join('\n')}\n`)
console.log(`proof dir: ${outDir}`)
