import assert from 'node:assert/strict'
import test from 'node:test'

import { CODEX_LINUX_LAUNCH, SCOPED_PERMISSION_HEADER, launcherPrompt } from '../src/launcherPrompts.js'

test('Codex copy prompt byte-preserves the package permission header and Linux block', () => {
  assert.equal(launcherPrompt('codex'), `${SCOPED_PERMISSION_HEADER}\n\n${CODEX_LINUX_LAUNCH}`)
  assert.match(CODEX_LINUX_LAUNCH, /cd "\$\{AOS_ROOT:-\/home\/liam\/agentic-os-live\}"/)
  assert.match(CODEX_LINUX_LAUNCH, /codex --sandbox workspace-write --ask-for-approval never$/)
  assert.match(SCOPED_PERMISSION_HEADER, /^PERMISSION MODE — SCOPED LOCAL TASK APPROVED/)
})

test('Claude copy prompt retains the exact same permission header and Linux-only root', () => {
  const prompt = launcherPrompt('claude-code')
  assert.ok(prompt.startsWith(`${SCOPED_PERMISSION_HEADER}\n\n`))
  assert.match(prompt, /cd "\$\{AOS_ROOT:-\/home\/liam\/agentic-os-live\}"/)
  assert.doesNotMatch(prompt, /\/mnt\/c|Windows Start|C:\\/)
})
