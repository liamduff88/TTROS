// Revisit: when the Memory Board browser editing contract changes. · Last touched: 2026-07-31.
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const repoRoot = '/home/liam/agentic-os-live'
const vaultRoot = '/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain'
const proofDir = path.join(repoRoot, 'proofs', 'memory-board-editing', '2026-07-31')
const baseUrl = process.env.MEMORY_BOARD_BASE_URL || 'http://127.0.0.1:3010'
const apiUrl = process.env.MEMORY_BOARD_API_URL || 'http://127.0.0.1:8010'
const targets = [
  { pointer: 'business_brain:memory/company.md', relative: 'memory/company.md', marker: '<!-- memory-board-proof-company-2026-07-31 -->' },
  { pointer: 'business_brain:memory/delivery_model.md', relative: 'memory/delivery_model.md', marker: '<!-- memory-board-proof-delivery-2026-07-31 -->' },
]

const sha256 = value => crypto.createHash('sha256').update(value).digest('hex')
const originals = new Map(targets.map(target => [target.pointer, fs.readFileSync(path.join(vaultRoot, target.relative), 'utf8')]))
const api = async (pathname, options = {}) => {
  const response = await fetch(`${apiUrl}${pathname}`, options)
  const payload = await response.json()
  if (!response.ok) throw new Error(`${response.status}: ${payload.detail || JSON.stringify(payload)}`)
  return payload
}

fs.mkdirSync(proofDir, { recursive: true })
const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const consoleErrors = []
const failedResponses = []
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('response', response => { if (response.status() >= 400) failedResponses.push({ url: response.url(), status: response.status() }) })

const openNote = async pointer => {
  await page.locator('button').filter({ hasText: pointer }).click()
  await page.getByRole('button', { name: 'Edit' }).waitFor()
}

const saveEditor = async pointer => {
  const responsePromise = page.waitForResponse(response => response.url().includes('/api/dashboard/memory/save') && response.request().method() === 'POST')
  await page.getByRole('button', { name: /^Save$/ }).click()
  const response = await responsePromise
  assert.equal(response.status(), 200)
  const payload = await response.json()
  await page.getByTestId('memory-save-state').filter({ hasText: `Saved ${pointer}` }).waitFor()
  return payload
}

const roundTrip = async target => {
  const canonicalPath = path.join(vaultRoot, target.relative)
  const original = originals.get(target.pointer)
  const edited = `${original}${original.endsWith('\n') ? '' : '\n'}${target.marker}\n`

  await openNote(target.pointer)
  await page.getByRole('button', { name: 'Edit' }).click()
  const editor = page.getByTestId('memory-markdown-editor')
  assert.equal(await editor.inputValue(), original)
  await editor.fill(edited)
  const saved = await saveEditor(target.pointer)
  assert.equal(fs.readFileSync(canonicalPath, 'utf8'), edited)

  await page.getByTitle('Close detail').click()
  await openNote(target.pointer)
  await page.getByRole('button', { name: 'Edit' }).click()
  assert.equal(await page.getByTestId('memory-markdown-editor').inputValue(), edited)
  assert.equal(fs.readFileSync(canonicalPath, 'utf8'), edited)
  await page.screenshot({ path: path.join(proofDir, `${path.basename(target.relative, '.md')}-saved-and-reopened.png`), fullPage: true })

  await page.getByTestId('memory-markdown-editor').fill(original)
  const restored = await saveEditor(target.pointer)
  await page.getByTitle('Close detail').click()
  await openNote(target.pointer)
  await page.getByRole('button', { name: 'Edit' }).click()
  assert.equal(await page.getByTestId('memory-markdown-editor').inputValue(), original)
  assert.equal(fs.readFileSync(canonicalPath, 'utf8'), original)
  await page.getByTitle('Close detail').click()

  return {
    pointer: target.pointer,
    canonical_path: canonicalPath,
    loaded_full_markdown_bytes: Buffer.byteLength(original),
    marker: target.marker,
    original_sha256: sha256(original),
    saved_sha256: sha256(edited),
    restored_sha256: sha256(fs.readFileSync(canonicalPath, 'utf8')),
    save_refresh: saved.refresh,
    restore_refresh: restored.refresh,
    saved_reopened_in_browser: true,
    restored_reopened_in_browser: true,
  }
}

let evidence
try {
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await page.locator('aside').getByRole('button', { name: 'Memory Board' }).click()
  await page.getByText('Canonical notes').waitFor()
  const listing = await api('/api/dashboard/memory')
  const listedPointers = listing.files.map(item => item.path)
  assert.equal(listedPointers.some(pointer => pointer.toLowerCase().includes('_backups/')), false)
  for (const target of targets) assert.equal(listedPointers.includes(target.pointer), true)

  const results = []
  for (const target of targets) results.push(await roundTrip(target))

  const repoLocalCandidates = [
    path.join(repoRoot, 'memory', 'company.md'),
    path.join(repoRoot, 'memory', 'delivery_model.md'),
    path.join(repoRoot, 'business_brain', 'memory', 'company.md'),
    path.join(repoRoot, 'business_brain', 'memory', 'delivery_model.md'),
  ]
  const existingRepoLocalCopies = repoLocalCandidates.filter(candidate => fs.existsSync(candidate))
  assert.deepEqual(existingRepoLocalCopies, [])
  assert.deepEqual(consoleErrors, [])
  assert.deepEqual(failedResponses, [])

  evidence = {
    success: true,
    timestamp: new Date().toISOString(),
    canonical_vault: vaultRoot,
    listed_note_count: listedPointers.length,
    backups_exposed: false,
    existing_repo_local_copies: existingRepoLocalCopies,
    results,
    console_errors: consoleErrors,
    failed_responses: failedResponses,
    screenshots: results.map(result => `${path.basename(result.canonical_path, '.md')}-saved-and-reopened.png`),
    token_usage_text: 'Token usage: no agent invocation',
  }
} finally {
  for (const target of targets) {
    const canonicalPath = path.join(vaultRoot, target.relative)
    const original = originals.get(target.pointer)
    if (fs.readFileSync(canonicalPath, 'utf8') === original) continue
    try {
      const loaded = await api(`/api/dashboard/memory/note?path=${encodeURIComponent(target.pointer)}`)
      await api('/api/dashboard/memory/save', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ path: target.pointer, content: original, expected_revision: loaded.revision }),
      })
    } catch {
      fs.writeFileSync(canonicalPath, original, 'utf8')
    }
    assert.equal(fs.readFileSync(canonicalPath, 'utf8'), original)
  }
  await browser.close()
}

fs.writeFileSync(path.join(proofDir, 'browser-evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(evidence, null, 2)}\n`)
