import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

test('persistent capture box is explicit and separate from queue commands', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { default: CaptureBox } = await vite.ssrLoadModule('/src/components/CaptureBox.jsx')
  const markup = renderToStaticMarkup(React.createElement(CaptureBox))

  assert.match(markup, /data-testid="cockpit-capture-box"/)
  assert.match(markup, /Capture a note to the Business Brain inbox/)
  assert.match(markup, /Capture a note… Ctrl\+Enter/)
  assert.match(markup, />Capture<\/button>/)
  assert.match(markup, /data-testid="quick-add-file-input"/)
  assert.match(markup, /multiple=""/)
  assert.match(markup, /data-testid="quick-add-browse"/)
  assert.match(markup, />Attach \/ Browse<\/button>/)
  assert.equal(markup.includes('Create queue item'), false)
})

test('quick add reuses shared upload and governed Memory Intake APIs with isolated per-file outcomes', async () => {
  const source = await import('node:fs').then(fs => fs.readFileSync(new URL('../src/components/CaptureBox.jsx', import.meta.url), 'utf8'))
  assert.match(source, /uploadFile\(row\.file\)/)
  assert.match(source, /ingestMemoryIntakeUpload\(uploaded\.upload_id\)/)
  assert.match(source, /for \(const row of fileBatch\)/)
  assert.match(source, /data-testid="quick-add-file-row"/)
  assert.match(source, /onDrop=\{event =>/)
  assert.match(source, /event\.dataTransfer\.files/)
  assert.match(source, /Remove \$\{row\.file\.name\}/)
  assert.match(source, /Note failed:/)
  assert.match(source, /need.*attention/i)
})
