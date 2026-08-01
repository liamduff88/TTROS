// Revisit: when the Memory Board editor contract changes. · Last touched: 2026-07-31.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const viewSource = fs.readFileSync(new URL('../src/views/DashboardV1.jsx', import.meta.url), 'utf8')
const apiSource = fs.readFileSync(new URL('../src/api.js', import.meta.url), 'utf8')

test('Memory Board loads and saves full canonical Markdown with visible state', () => {
  assert.match(apiSource, /getDashboardMemoryNote/)
  assert.match(apiSource, /\/dashboard\/memory\/note/)
  assert.match(apiSource, /saveDashboardMemory/)
  assert.match(apiSource, /\/dashboard\/memory\/save/)
  assert.match(viewSource, /getDashboardMemoryNote\(item\.path\)/)
  assert.match(viewSource, /expected_revision: selected\.revision/)
  assert.match(viewSource, /data-testid="memory-markdown-editor"/)
  assert.match(viewSource, /data-testid="memory-save-state"/)
  assert.match(viewSource, /requestError\.response\?\.data\?\.detail/)
})
