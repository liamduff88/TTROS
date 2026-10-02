// Revisit: when the Memory entity browser contract changes. · Last touched: 2026-10-02.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const view = fs.readFileSync(new URL('../src/views/MemoryBrain.jsx', import.meta.url), 'utf8')
const hubs = fs.readFileSync(new URL('../src/views/Hubs.jsx', import.meta.url), 'utf8')
const api = fs.readFileSync(new URL('../src/api.js', import.meta.url), 'utf8')

test('Memory tab is the entity-first browser', () => {
  assert.match(hubs, /id: 'memory', label: 'Memory', component: MemoryBrain/)
  assert.match(view, /Search people, companies, projects, topics or files…/)
  assert.match(view, /data-testid="memory-entity-view"/)
  assert.match(view, /data-testid="memory-files-view"/)
})

test('Memory browser only uses deterministic local endpoints', () => {
  for (const route of ['/memory/search', '/memory/entity', '/memory/document', '/memory/browse', '/memory/open']) assert.ok(api.includes(route), route)
  assert.doesNotMatch(view, /askDavid|askHermes|consultExecutive|wslHermes|wslClaude|wslCodex/)
})

test('Ambiguous names are disambiguated, never merged', () => {
  assert.match(view, /data\.resolution === 'single' && only\?\.match === 'exact'/)
  assert.match(view, /choose one/)
  assert.match(view, /not merged/i)
})

test('Reader shows the full document with Windows actions and gated edit', () => {
  assert.match(view, /getMemoryDocument\(path\)/)
  assert.match(view, /Open in Windows/)
  assert.match(view, /Open containing folder/)
  assert.match(view, /Copy Windows path/)
  assert.match(view, /data\.editable && !editing/)
  assert.match(view, /expected_revision: data\.revision/)
})

test('Timeline keeps import-only dates out of the chronology', () => {
  assert.match(view, /data-testid="memory-import-dated"/)
  assert.match(view, /Event date not recorded · import date only/)
  assert.match(view, /oldestFirst/)
})

test('Read-only reason is shown and the existing canonical-notes board stays reachable', () => {
  assert.match(view, /data\.edit_block_reason/)
  assert.match(view, /\['canonical', 'Canonical notes'\]/)
  assert.match(view, /<MemoryBoard \/>/)
})
