// Revisit: when the Memory Intake page, its Cockpit quick-drop card, or the
// shared upload contract changes. · Created 2026-09-13.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')

const apiSource = read('../src/api.js')
const appSource = read('../src/App.jsx')
const shellSource = read('../src/shellState.js')
const hubsSource = read('../src/views/Hubs.jsx')
const memoryIntakeSource = read('../src/views/MemoryIntake.jsx')
const dashboardV1Source = read('../src/views/DashboardV1.jsx')

test('the shared upload mechanism is exposed once, sending real bytes via FormData', () => {
  assert.match(apiSource, /export const uploadFile = file => \{/)
  assert.match(apiSource, /new FormData\(\)/)
  assert.match(apiSource, /form\.append\('file', file\)/)
  assert.match(apiSource, /apiUpload\.post\('\/uploads', form\)/)
})

test('Memory Intake API surface reuses the one memory-intake/uploads backend contract', () => {
  assert.match(apiSource, /export const getMemoryIntake = \(\) => api\.get\('\/memory-intake'\)/)
  assert.match(apiSource, /export const ingestMemoryIntakeUpload = upload_id => apiIngest\.post\('\/memory-intake\/ingest', \{ upload_id \}\)/)
  assert.match(apiSource, /export const ingestMemoryIntakeInboxPath = inbox_path => apiIngest\.post\('\/memory-intake\/ingest', \{ inbox_path \}\)/)
  assert.match(apiSource, /export const getUpload = upload_id => api\.get\(`\/uploads\/\$\{encodeURIComponent\(upload_id\)\}`\)/)
})

test('Add to Memory is reachable as a Search-hub local tab via the existing internal route', () => {
  assert.match(shellSource, /'memory-intake': \{ label: 'Add to Memory'/)
  assert.match(shellSource, /'memory-intake': 'search'/)
  assert.match(hubsSource, /import MemoryIntake from '\.\/MemoryIntake'/)
  assert.match(hubsSource, /id: 'add-to-memory', label: 'Add to Memory', component: MemoryIntake/)
  assert.match(appSource, /'memory-intake': withTab\(SearchHub, 'add-to-memory'\)/)
})

test('the Memory Intake page supports drop, browse, multi-select, ingest-selected, and preview', () => {
  assert.match(memoryIntakeSource, /data-testid="memory-intake-dropzone"/)
  assert.match(memoryIntakeSource, /onDrop=\{onDrop\}/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-file-input"/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-select-all"/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-ingest-selected"/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-ready-list"/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-unfiled-list"/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-recent-list"/)
  assert.match(memoryIntakeSource, /Ingest to Business Brain/)
})

test('New & Unfiled never auto-ingests -- ingestion is always one explicit click per row', () => {
  assert.match(memoryIntakeSource, /disabled=\{!row\.supported \|\| row\.already_in_brain \|\| busyKeys\.has/)
  assert.doesNotMatch(memoryIntakeSource, /useEffect\([^)]*ingestInbox/)
})

test('the Business Brain index integrity signal is surfaced to the operator, not just logged', () => {
  assert.match(memoryIntakeSource, /brain_index_integrity/)
  assert.match(memoryIntakeSource, /data-testid="memory-intake-integrity-warning"/)
  assert.match(memoryIntakeSource, /!integrity\.ok/)
})

test('partial semantic failures are shown as needs-attention, never as ingested', () => {
  assert.match(memoryIntakeSource, /needs_attention: 'Blocked'/)
  assert.match(memoryIntakeSource, /needs_attention: 'Needs attention'/)
  assert.match(memoryIntakeSource, /row\.source_card_present \? 'verified'/)
})

test('the Cockpit quick-drop card is compact, supports drop and browse, and links to the full page', () => {
  assert.match(memoryIntakeSource, /export function MemoryIntakeQuickDropCard/)
  assert.match(memoryIntakeSource, /data-testid="cockpit-memory-intake-card"/)
  assert.match(memoryIntakeSource, /data-testid="cockpit-memory-intake-browse"/)
  assert.match(memoryIntakeSource, /data-testid="cockpit-memory-intake-ready-count"/)
  assert.match(memoryIntakeSource, /data-testid="cockpit-memory-intake-ingested-count"/)
  assert.match(memoryIntakeSource, /onNavigate\?\.\('memory-intake'\)/)
})

test('Cockpit stays limited to the David/Needs Me/Active Work/Recent Results hierarchy and does not re-mount the quick-drop card', () => {
  assert.doesNotMatch(dashboardV1Source, /MemoryIntakeQuickDropCard/)
})
