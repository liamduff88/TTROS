// One-off evidence script for the Work Queue UX repair task (sticky tab gap,
// parent/child grouping, human-readable titles, business-outcome list
// labels, requested-delivery evidence, report section priority). Mocks the
// backend with fixture data shaped exactly like the real AOS-2026-0497/0498
// Internal Outreach Daily records (see queue/work_items.jsonl) plus one
// deliberate telegram-delivery-request fixture to rehearse the negative and
// positive delivery-evidence cases per repo evidence-discipline rules.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseUrl = process.env.WQ_PROOF_BASE_URL || 'http://127.0.0.1:3011'
const screenshotDir = process.env.WQ_PROOF_SCREENSHOT_DIR || '/tmp/wq-proof'

const hash = value => value.repeat(64).slice(0, 64)

const parentId = 'AOS-2026-0497'
const childId = 'AOS-2026-0498'
const parentTitle = 'Run Internal Outreach Daily to verified no-send outcome'
const childTitle = 'Run Internal Outreach Daily'

const reportMarkdown = `# ${childId} — Internal Outreach Daily local no-send review package

Run timestamp: 2026-09-12T01:55:13Z
Mode: local no-send; approved local inputs only.

## Approval and safety gates preserved

- Zero sends: confirmed. No email, LinkedIn message, or other external side effect was performed.
- Zero connector mutation: confirmed.

## Local evidence reviewed

- workflows/internal_outreach_daily/workflow.md lines 13-25.

## Selected outreach candidates

Selected N=5 from existing local evidence.

### 1. Nicolas Dupont — Cyborg

Evidence reviewed: first sales-leader role.

### 2. Parminder Singh — DeepInspect.AI

Evidence reviewed: founding Account Executive role.

### 3. Ilan Puterman — Club Hub

Evidence reviewed: first sales hire.

### 4. Omar Alani — Zunesha Labs

Evidence reviewed: founding Account Executive role.

### 5. Anush Sridhar — Manufex

Evidence reviewed: founding Account Executive role.

## Verification checks performed

- Read workflow/skill gates.

## Receipt block

PASS

Work item:
- ${childId}
`

const items = [
  {
    id: parentId,
    title: parentTitle,
    status: 'done',
    owner: 'hermes',
    priority: 8,
    parent_id: null,
    tags: ['executive_objective', 'hermes_chain', 'parent'],
    lane: 'unassigned',
    source: 'dashboard/hermes_message',
    created_at: '2026-09-12T01:53:48Z',
    updated_at: '2026-09-12T01:57:59Z',
    context: 'Run the Internal Outreach Daily workflow to completion and return the verified outcome.',
    record_hash: hash('p'),
  },
  {
    id: childId,
    title: childTitle,
    status: 'done',
    owner: 'revenue',
    priority: 5,
    parent_id: parentId,
    step_index: 1,
    tags: ['async_dispatch', 'executive_objective_child', 'hermes_chain', 'internal_outreach_daily'],
    lane: 'revenue',
    source: 'dashboard/hermes_message',
    created_at: '2026-09-12T01:53:49Z',
    updated_at: '2026-09-12T01:57:24Z',
    context: 'Execute the existing Internal Outreach Daily workflow end-to-end.',
    record_hash: hash('c'),
  },
  // A second, unrelated fixture that DOES contain delivery-request language,
  // to rehearse the positive case for the requested-delivery detector (the
  // real Internal Outreach Daily item has no such evidence at all).
  {
    id: 'AOS-2026-0700',
    title: 'Run Weekly Digest and notify Liam',
    status: 'done',
    owner: 'delivery',
    priority: 4,
    parent_id: null,
    tags: [],
    lane: 'delivery',
    source: 'dashboard/hermes_message',
    created_at: '2026-09-10T09:00:00Z',
    updated_at: '2026-09-10T09:05:00Z',
    context: 'Please send me a Telegram message with the .md file attached once this is done.',
    record_hash: hash('t'),
  },
]

const detailFor = id => {
  const base = items.find(row => row.id === id)
  if (!base) return null
  if (id === parentId) {
    return {
      ...base,
      detail_loaded: true,
      receipts: [{ path: `queue/receipts/${parentId}-executive-objective.md`, status: 'done', created_at: base.updated_at }],
      run_artifacts: [],
      primary_artifact: null,
      summary_for_operator: 'Executive result\n\nInternal Outreach Daily completed successfully as a local, no-send review package.',
      final_result: null,
      pipeline: {
        mode: 'workflow_chain',
        parent_id: parentId,
        nodes: [
          { id: parentId, name: parentTitle, status: 'done', updated_at: base.updated_at, depends_on: [], receipts: [], artifacts: [] },
          { id: childId, name: childTitle, status: 'done', updated_at: '2026-09-12T01:57:24Z', depends_on: [], receipts: [], artifacts: [] },
        ],
        history: [],
      },
    }
  }
  if (id === childId) {
    return {
      ...base,
      detail_loaded: true,
      receipts: [{ path: `queue/receipts/${childId}.md`, status: 'done', created_at: base.updated_at }],
      run_artifacts: [
        { path: `workflows/queue_artifacts/${childId}_Run_Internal_Outreach_Daily.md`, available: true, category: 'business_result', extension: '.md', name: `${childId}_Run_Internal_Outreach_Daily.md`, size_bytes: reportMarkdown.length },
      ],
      primary_artifact: { path: `workflows/queue_artifacts/${childId}_Run_Internal_Outreach_Daily.md`, available: true, content: reportMarkdown, extension: '.md' },
      summary_for_operator: 'Ran the Internal Outreach Daily workflow locally in no-send mode; five candidates selected.',
      final_result: null,
      pipeline: { mode: 'workflow_chain', parent_id: parentId, nodes: [], history: [] },
    }
  }
  return {
    ...base,
    detail_loaded: true,
    receipts: [],
    run_artifacts: [],
    primary_artifact: null,
    summary_for_operator: 'Weekly digest generated locally.',
    final_result: null,
    pipeline: { mode: 'status_fallback', parent_id: id, nodes: [], history: [] },
  }
}

const statuses = ['inbox', 'agent_todo', 'agent_working', 'needs_input', 'human_review', 'done', 'blocked', 'cancelled']
const counts = () => Object.fromEntries(statuses.map(status => [status, items.filter(item => item.status === status).length]))
const response = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
await page.addInitScript(() => {
  sessionStorage.setItem('aos.dashboard.shell.v1', JSON.stringify({
    view: 'work-queue',
    viewParams: {},
    sessionTabs: [
      { id: 'cockpit', label: 'Cockpit', workbench: 'hermes', preview: false },
      { id: 'work-queue', label: 'Work Queue', workbench: 'codex', preview: true, params: {} },
    ],
  }))
})

await page.route('**/api/**', async route => {
  const request = route.request()
  const url = new URL(request.url())
  if (url.pathname === '/api/queue/items' && request.method() === 'GET') {
    await route.fulfill(response({ success: true, scope: 'all', items, itemCount: items.length, totalCount: items.length }))
    return
  }
  if (['/api/queue/status', '/api/queue/summary'].includes(url.pathname)) {
    await route.fulfill(response({ success: true, counts: counts(), totalCount: items.length, activeCount: 0, needsLiam: 0, nextItem: null }))
    return
  }
  const match = url.pathname.match(/^\/api\/queue\/items\/([^/]+)$/)
  if (match && request.method() === 'GET') {
    const item = detailFor(decodeURIComponent(match[1]))
    await route.fulfill(response(item ? { success: true, item } : { detail: 'not found' }, item ? 200 : 404))
    return
  }
  if (url.pathname === '/api/queue/artifact' && request.method() === 'GET') {
    const path = url.searchParams.get('path') || ''
    if (path.includes(childId)) {
      await route.fulfill(response({ success: true, path, content: reportMarkdown, is_binary: false, content_type: 'text/markdown', extension: '.md' }))
      return
    }
    await route.fulfill(response({ success: false, reason: 'not found' }, 404))
    return
  }
  await route.fulfill(response({ success: true, counts: counts(), queue_items: items, needs_me: [] }))
})

const results = { screenshot_dir: screenshotDir }
const consoleErrors = []
page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()) })
page.on('pageerror', err => consoleErrors.push(String(err)))

const expandList = async () => {
  // Selecting any item auto-collapses the left list (existing, intentional
  // behavior — see Queue.jsx's `if (selectedId) setListCollapsed(true)`
  // effect), so any assertion reading a card's full body text must
  // re-expand it first.
  const btn = page.getByRole('button', { name: /Expand work items/ })
  if (await btn.count()) await btn.click()
}

try {
  await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle' })
  await page.getByTestId('queue-content-tabs').waitFor()
  await expandList()

  // --- Claim 1: exactly one top-level card for the parent+child pair ------
  const parentCards = await page.locator(`[data-queue-card-id="${parentId}"]`).count()
  const childCards = await page.locator(`[data-queue-card-id="${childId}"]`).count()
  results.parent_card_count = parentCards
  results.child_card_count_in_list = childCards
  assert.equal(parentCards, 1, 'expected exactly one parent card')
  assert.equal(childCards, 0, 'expected the child NOT to render as a separate top-level card')

  // --- Claim 2: list does not lead with an AOS ID ---------------------------
  const cardText = await page.locator(`[data-queue-card-id="${parentId}"]`).innerText()
  const firstLine = cardText.split('\n')[0].trim()
  results.parent_card_first_line = firstLine
  assert.equal(firstLine, parentTitle)
  assert.doesNotMatch(firstLine, /^AOS-\d{4}-\d+/)

  // --- Claim 3: sticky tab strip has no gap once stuck ----------------------
  const tabStrip = page.getByTestId('queue-content-tabs')
  const beforeScroll = await tabStrip.boundingBox()
  await page.evaluate(() => document.getElementById('aos-main-scroll').scrollTo({ top: 900 }))
  await page.waitForTimeout(150)
  const afterScroll = await tabStrip.boundingBox()
  const mainBox = await page.evaluate(() => {
    const el = document.getElementById('aos-main-scroll')
    const rect = el.getBoundingClientRect()
    return { top: rect.top }
  })
  results.tab_strip_before_scroll_top = beforeScroll.y
  results.tab_strip_after_scroll_top = afterScroll.y
  results.main_scroll_viewport_top = mainBox.top
  results.gap_above_sticky_tabs_px = Math.round((afterScroll.y - mainBox.top) * 100) / 100
  assert.ok(afterScroll.y < beforeScroll.y, 'tab strip should have moved up while scrolling')
  assert.ok(Math.abs(afterScroll.y - mainBox.top) < 1, `expected the stuck tab strip flush with the scrollport top, gap was ${results.gap_above_sticky_tabs_px}px`)

  // --- Claim 4: selecting the grouped card shows Steps for both records ----
  await page.locator(`[data-queue-card-id="${parentId}"]`).click()
  await page.getByTestId('queue-selected-detail').waitFor()
  await page.waitForFunction(id => document.querySelector(`[data-selected-item-id="${id}"]`), parentId)
  const steps = page.getByTestId('workflow-steps-summary')
  await steps.waitFor()
  const stepsText = await steps.innerText()
  results.steps_section_text = stepsText
  assert.match(stepsText, new RegExp(parentTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.match(stepsText, new RegExp(childTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))

  // --- Claim 5: business-outcome list line appears once the child is opened
  await steps.getByRole('button', { name: childTitle }).click()
  await page.waitForFunction(id => document.querySelector(`[data-selected-item-id="${id}"]`), childId)
  results.console_errors = consoleErrors.slice()
  await page.waitForTimeout(200)
  await page.getByRole('button', { name: /Expand work items/ }).click()
  const outcomeLine = await page.locator(`[data-queue-card-id="${parentId}"]`).innerText()
  results.list_card_after_child_opened = outcomeLine
  assert.match(outcomeLine, /5 outreach candidates selected/)

  // --- Claim 6: report visual priority — highlight banner + demoted section
  const openReportButton = page.getByTestId('open-primary-result')
  await openReportButton.waitFor()
  await openReportButton.click()
  const highlight = page.getByTestId('report-result-highlight')
  await highlight.waitFor()
  results.report_highlight_text = await highlight.innerText()
  assert.match(results.report_highlight_text, /5 selected/)
  const demoted = page.getByTestId('demoted-report-section').first()
  await demoted.waitFor()
  const demotedOpenBefore = await demoted.evaluate(el => el.open)
  results.demoted_section_open_by_default = demotedOpenBefore
  assert.equal(demotedOpenBefore, false, 'safety/verification section should be collapsed by default')
  const visibleSelectedHeading = await page.getByTestId('artifact-markdown-body').getByText('Selected outreach candidates').isVisible()
  results.selected_candidates_heading_visible_without_expanding = visibleSelectedHeading
  assert.ok(visibleSelectedHeading)

  // --- Claim 7a: requested-delivery block absent when no evidence exists ---
  await page.getByTestId('queue-content-tabs').getByText('Work Queue', { exact: true }).click()
  await page.getByTestId('queue-selected-detail').waitFor()
  const deliveryBlockOnRealItem = await page.getByTestId('requested-delivery-status').count()
  results.requested_delivery_block_present_for_internal_outreach_daily = deliveryBlockOnRealItem > 0
  assert.equal(deliveryBlockOnRealItem, 0, 'must not invent a delivery status when no request evidence exists')

  // --- Claim 7b: requested-delivery block appears (and is honest) when the
  // item's own request text names a channel with no completion evidence ----
  await page.locator('[data-queue-card-id="AOS-2026-0700"]').click()
  await page.waitForFunction(() => document.querySelector('[data-selected-item-id="AOS-2026-0700"]'))
  const deliveryBlock = page.getByTestId('requested-delivery-status')
  await deliveryBlock.waitFor()
  results.delivery_evidence_positive_case_text = await deliveryBlock.innerText()
  assert.match(results.delivery_evidence_positive_case_text, /telegram/i)
  assert.match(results.delivery_evidence_positive_case_text, /not completed/i)

  // --- Claim 8: mobile viewport still usable --------------------------------
  await page.setViewportSize({ width: 390, height: 844 })
  await page.locator(`[data-queue-card-id="${parentId}"]`).click()
  await page.waitForFunction(id => document.querySelector(`[data-selected-item-id="${id}"]`), parentId)
  const horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)
  results.mobile_horizontal_overflow = horizontalOverflow
  assert.equal(horizontalOverflow, false)

  process.stdout.write(`${JSON.stringify({ success: true, ...results }, null, 2)}\n`)
} catch (error) {
  await page.screenshot({ path: `${screenshotDir}/failure.png`, fullPage: true }).catch(() => {})
  process.stdout.write(`${JSON.stringify({ success: false, error: String(error?.message || error), ...results }, null, 2)}\n`)
  process.exitCode = 1
} finally {
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await browser.close()
}
