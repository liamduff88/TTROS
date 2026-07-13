import test from 'node:test'
import assert from 'node:assert/strict'
import { MAX_SESSION_TABS, closeSessionTab, initialSessionTabs, laneName, needsMeCollapseKey, openSessionTab, pinSessionTab, restoreShellSession, shellSessionSnapshot, workbenchColor } from '../src/shellState.js'

test('Cockpit stays pinned first and cannot close', () => {
  const tabs = initialSessionTabs()
  assert.equal(tabs[0].id, 'cockpit')
  assert.equal(tabs[0].pinned, true)
  assert.deepEqual(closeSessionTab(tabs, 'cockpit'), tabs)
})

test('preview navigation reuses the single preview tab', () => {
  const initial = initialSessionTabs()
  const queue = openSessionTab(initial, 'work-queue')
  assert.equal(queue.length, 2)
  assert.equal(queue[1].id, 'work-queue')
  const artifacts = openSessionTab(queue, 'artifacts')
  assert.equal(artifacts.length, 2)
  assert.equal(artifacts[1].id, 'artifacts')
})

test('pinned tabs persist, close, and enforce the eight-tab cap', () => {
  let tabs = pinSessionTab(openSessionTab(initialSessionTabs(), 'work-queue'), 'work-queue')
  for (const id of ['workflow-bench', 'skills-board', 'memory-board', 'prompt-library', 'graphify', 'repo-ingest', 'results-receipts', 'tokens-roi', 'artifacts']) {
    tabs = pinSessionTab(openSessionTab(tabs, id), id)
  }
  assert.equal(tabs.length, MAX_SESSION_TABS)
  assert.equal(tabs[0].id, 'cockpit')
  tabs = closeSessionTab(tabs, 'work-queue')
  assert.equal(tabs.some(tab => tab.id === 'work-queue'), false)
})

test('two-axis helpers keep lane separate and review amber overrides workbench', () => {
  assert.equal(laneName({ tags: ['dashboard', 'lane:revenue'] }), 'revenue')
  assert.equal(workbenchColor('codex', 'agent_working'), 'var(--wb-codex-working)')
  assert.equal(workbenchColor('claude', 'done'), 'var(--wb-claude-done)')
  assert.equal(workbenchColor('codex', 'human_review'), 'var(--needs-review)')
  assert.equal(workbenchColor(null, 'done'), 'var(--hairline)')
})

test('session restoration preserves a routed Work Queue selection across refresh and tab return', () => {
  const tabs = openSessionTab(initialSessionTabs(), 'work-queue', { selectedId: 'AOS-2026-0078' })
  const restored = restoreShellSession(shellSessionSnapshot('work-queue', { selectedId: 'AOS-2026-0078' }, tabs))
  assert.equal(restored.view, 'work-queue')
  assert.equal(restored.viewParams.selectedId, 'AOS-2026-0078')
  assert.equal(restored.sessionTabs.find(tab => tab.id === 'work-queue').params.selectedId, 'AOS-2026-0078')
})

test('Needs Me auto-collapse is keyed only to a selected Work Queue item', () => {
  assert.equal(needsMeCollapseKey('work-queue', { selectedId: 'AOS-2026-0087' }), 'AOS-2026-0087')
  assert.equal(needsMeCollapseKey('work-queue', {}), null)
  assert.equal(needsMeCollapseKey('cockpit', { selectedId: 'AOS-2026-0087' }), null)
})

test('invalid stored shell state falls back safely', () => {
  assert.equal(restoreShellSession('{bad json').view, 'message-board')
  assert.equal(restoreShellSession({ view: 'not-a-view', sessionTabs: [] }).sessionTabs[0].id, 'cockpit')
})
