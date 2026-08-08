// Revisit: when the Cockpit Executive Team consultation contract changes. · Last touched: 2026-08-01.

import assert from 'node:assert/strict'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import {
  EXECUTIVE_TEAM_MEMBERS,
  canSubmitExecutiveConsultation,
  executiveApiError,
  executiveConsultationReducer,
  initialExecutiveConsultation,
} from '../src/executiveTeamState.js'

test('five permanent specialist cards map exactly to named profiles and render without queue data', async t => {
  assert.deepEqual(
    EXECUTIVE_TEAM_MEMBERS.map(member => [member.name, member.profile]),
    [
      ['Revenue', 'aos-revenue'],
      ['Marketing', 'aos-marketing'],
      ['Delivery', 'aos-delivery'],
      ['Operations', 'aos-ops'],
      ['Executive Team', 'aos-orchestrator'],
    ],
  )
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { default: ExecutiveTeam } = await vite.ssrLoadModule('/src/components/ExecutiveTeam.jsx')
  const markup = renderToStaticMarkup(React.createElement(ExecutiveTeam))
  assert.match(markup, /data-testid="executive-team"/)
  assert.equal((markup.match(/data-executive-card=/g) || []).length, 5)
  for (const member of EXECUTIVE_TEAM_MEMBERS) {
    assert.match(markup, new RegExp(`data-executive-card="${member.id}"[^>]*data-profile="${member.profile}"`))
  }
  assert.equal(markup.includes('queue item'), false)
})

test('selected composer state covers loading success failure and duplicate-submit guard', () => {
  const loading = executiveConsultationReducer(initialExecutiveConsultation, { type: 'start' })
  assert.equal(loading.status, 'loading')
  assert.equal(canSubmitExecutiveConsultation(loading, 'question'), false)
  const success = executiveConsultationReducer(loading, { type: 'success', result: { actual_profile: 'aos-revenue' } })
  assert.equal(success.status, 'success')
  assert.equal(success.result.actual_profile, 'aos-revenue')
  const failure = executiveConsultationReducer(loading, { type: 'failure', error: 'HTTP 401', result: { fallback_occurred: false } })
  assert.equal(failure.status, 'failure')
  assert.equal(failure.error, 'HTTP 401')
  assert.equal(canSubmitExecutiveConsultation(failure, 'retry'), true)
})

test('honest API errors distinguish timeout missing route and backend unavailable', () => {
  assert.match(executiveApiError({ code: 'ECONNABORTED' }), /timed out/)
  assert.match(executiveApiError({ response: { status: 404, data: {} } }), /route is missing/)
  assert.match(executiveApiError({ message: 'Network Error' }), /backend is unavailable/)
})

test('component source exposes actual profile fallback evidence and in-flight duplicate guard', async () => {
  const source = await import('node:fs/promises').then(fs => fs.readFile(new URL('../src/components/ExecutiveTeam.jsx', import.meta.url), 'utf8'))
  assert.match(source, /Actual profile:/)
  assert.match(source, /Fallback:/)
  assert.match(source, /submissionRef\.current/)
  assert.match(source, /Retry safely/)
  assert.match(source, /executive_header_included/)
  assert.match(source, /executive_brief_included/)
})
