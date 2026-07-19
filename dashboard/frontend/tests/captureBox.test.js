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
  assert.equal(markup.includes('Create queue item'), false)
})
