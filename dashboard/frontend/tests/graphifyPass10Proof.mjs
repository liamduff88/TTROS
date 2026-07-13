// Revisit: when Graphify/Repo Ingest browser contracts change. · Last touched: 2026-07-13.
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const proofDir = '/home/liam/agentic-os-live/proofs/pass10-graphify'
fs.mkdirSync(proofDir, { recursive: true })

const browser = await chromium.launch({
  headless: true,
  executablePath: '/home/liam/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const context = await browser.newContext({ viewport: { width: 1680, height: 1100 }, deviceScaleFactor: 1 })
const page = await context.newPage()
page.setDefaultTimeout(10000)
const requests = []
const responseHeaders = {}
const consoleErrors = []
const failedResponses = []
page.on('request', request => requests.push({ url: request.url(), resourceType: request.resourceType(), frameUrl: request.frame().url() }))
page.on('response', async response => {
  if (response.status() >= 400) failedResponses.push({ url: response.url(), status: response.status() })
  if (response.url().includes('/api/graphify/artifacts/pallets/itsdangerous/graphify-out/')) responseHeaders[response.url()] = await response.allHeaders()
})
page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })

await page.goto('http://127.0.0.1:3010', { waitUntil: 'networkidle' })
await page.locator('aside').getByRole('button', { name: 'Repo Ingest' }).click()
await page.getByPlaceholder('https://github.com/owner/repository').fill('https://github.com/pallets/itsdangerous')
await page.getByText('Available: pallets/itsdangerous').waitFor()
const repoGraphLink = page.getByRole('link', { name: 'Graph', exact: true })
const repoGraphHref = await repoGraphLink.getAttribute('href')
const [repoGraphPage] = await Promise.all([page.waitForEvent('popup'), repoGraphLink.click()])
repoGraphPage.setDefaultTimeout(10000)
await repoGraphPage.waitForLoadState('domcontentloaded')
await repoGraphPage.locator('.node circle').last().click()
await repoGraphPage.locator('#details:not([hidden])').waitFor()
const repoGraphSelection = {
  title: await repoGraphPage.locator('#detail-title').innerText(),
  selectedNodes: await repoGraphPage.locator('.node.selected').count(),
  relatedEdges: await repoGraphPage.locator('.edge.related').count(),
}
if (repoGraphSelection.selectedNodes !== 1 || repoGraphSelection.relatedEdges < 1) throw new Error(`Repo Ingest Graph link is not interactive: ${JSON.stringify(repoGraphSelection)}`)
await repoGraphPage.close()
await page.screenshot({ path: path.join(proofDir, '01-repo-ingest-itsdangerous.png'), fullPage: true })

await page.locator('aside').getByRole('button', { name: 'Graphify' }).click()
await page.getByText('pallets/itsdangerous', { exact: true }).first().waitFor()
const graphFrameElement = page.getByTestId('graphify-graph-preview')
const treeFrameElement = page.getByTestId('graphify-tree-preview')
await graphFrameElement.waitFor()
await treeFrameElement.waitFor()
const waitForFrame = async fragment => {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const frame = page.frames().find(candidate => candidate.url().includes(fragment))
    if (frame) return frame
    await page.waitForTimeout(100)
  }
  return null
}
const graphFrame = await waitForFrame('/graphify-out/graph.html')
const treeFrame = await waitForFrame('/graphify-out/GRAPH_TREE.html')
if (!graphFrame || !treeFrame) throw new Error('Graph or tree preview frame did not load')
await graphFrame.locator('#stats').filter({ hasText: '211 nodes' }).waitFor()
await treeFrame.locator('#stats').filter({ hasText: '211 symbols' }).waitFor()
const graphCircles = await graphFrame.locator('circle').count()
const graphLines = await graphFrame.locator('line').count()
const treeGroups = await treeFrame.locator('details').count()
if (graphCircles < 50 || graphLines < 50 || treeGroups < 5) throw new Error(`Preview did not visibly render enough content: circles=${graphCircles}, lines=${graphLines}, treeGroups=${treeGroups}`)
await graphFrame.locator('.node circle').last().click()
await graphFrame.locator('#details:not([hidden])').waitFor()
const graphSelection = {
  title: await graphFrame.locator('#detail-title').innerText(),
  selectedNodes: await graphFrame.locator('.node.selected').count(),
  relatedEdges: await graphFrame.locator('.edge.related').count(),
}
const transformBeforeZoom = await graphFrame.locator('#viewport').getAttribute('transform')
await graphFrame.locator('#zoom-in').click()
const transformAfterZoom = await graphFrame.locator('#viewport').getAttribute('transform')
await graphFrame.locator('#reset').click()
const transformAfterReset = await graphFrame.locator('#viewport').getAttribute('transform')
if (graphSelection.selectedNodes !== 1 || graphSelection.relatedEdges < 1 || transformBeforeZoom === transformAfterZoom || transformAfterReset !== 'translate(0 0) scale(1)') throw new Error(`Embedded Graphify preview interaction failed: ${JSON.stringify({ graphSelection, transformBeforeZoom, transformAfterZoom, transformAfterReset })}`)
await graphFrame.locator('.node circle').last().click()
await page.getByTestId('graphify-artifact-links').scrollIntoViewIfNeeded()
await page.screenshot({ path: path.join(proofDir, '02-graphify-itsdangerous-graph-tree.png'), fullPage: true })

const graphSandbox = await graphFrameElement.getAttribute('sandbox')
const treeSandbox = await treeFrameElement.getAttribute('sandbox')
const externalRequests = requests.filter(request => {
  try {
    const url = new URL(request.url)
    return !['127.0.0.1', 'localhost'].includes(url.hostname) && !['data:', 'blob:', 'about:'].includes(url.protocol)
  } catch { return true }
})
const graphInitiatedRemoteRequests = requests.filter(request => request.frameUrl.includes('/api/graphify/artifacts/') && !request.url.startsWith('http://127.0.0.1:'))
const graphHeaders = Object.entries(responseHeaders).find(([url]) => url.endsWith('/graphify-out/graph.html'))?.[1] || {}
const treeHeaders = Object.entries(responseHeaders).find(([url]) => url.endsWith('/graphify-out/GRAPH_TREE.html'))?.[1] || {}
const artifactLabels = await page.getByTestId('graphify-artifact-links').innerText()
const evidence = {
  timestamp: new Date().toISOString(),
  repository: 'pallets/itsdangerous',
  iframe_sandbox: { graph: graphSandbox, tree: treeSandbox },
  content_security_policy: { graph: graphHeaders['content-security-policy'] || '', tree: treeHeaders['content-security-policy'] || '' },
  visible_render: { graphCircles, graphLines, treeGroups, graphStats: await graphFrame.locator('#stats').innerText(), treeStats: await treeFrame.locator('#stats').innerText() },
  interaction: { repoGraphHref, repoGraphSelection, graphSelection, transformBeforeZoom, transformAfterZoom, transformAfterReset },
  artifact_access_labels: artifactLabels,
  external_requests: externalRequests,
  graph_initiated_remote_requests: graphInitiatedRemoteRequests,
  failed_responses: failedResponses,
  console_errors: consoleErrors,
  screenshots: ['01-repo-ingest-itsdangerous.png', '02-graphify-itsdangerous-graph-tree.png'],
}
if (graphSandbox !== 'allow-scripts' || treeSandbox !== 'allow-scripts') throw new Error('Iframe sandbox contract failed')
if (!String(graphHeaders['content-security-policy'] || '').includes("connect-src 'none'") || !String(treeHeaders['content-security-policy'] || '').includes("connect-src 'none'")) throw new Error('Graph/tree CSP contract failed')
if (externalRequests.length || graphInitiatedRemoteRequests.length) throw new Error('Remote runtime request detected')
if (failedResponses.length || consoleErrors.length) throw new Error(`Browser errors detected: ${JSON.stringify({ failedResponses, consoleErrors })}`)
fs.writeFileSync(path.join(proofDir, 'browser-evidence.json'), JSON.stringify(evidence, null, 2) + '\n')
console.log(JSON.stringify(evidence, null, 2))
await browser.close()
