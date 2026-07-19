export const MAX_SESSION_TABS = 8

export const LANE_ROUTE_NAMES = ['marketing', 'revenue', 'delivery', 'operations', 'unassigned']

const normalizeLaneRouteName = value => {
  const lane = String(value || '').trim().toLowerCase()
  return LANE_ROUTE_NAMES.includes(lane) ? lane : null
}

export const laneRoutePath = lane => {
  const normalized = normalizeLaneRouteName(lane)
  return normalized ? `/lane/${normalized}` : null
}

export const shellRouteFromPath = pathname => {
  const match = String(pathname || '').match(/^\/lane\/([^/]+)\/?$/)
  if (!match) return null
  let lane
  try {
    lane = normalizeLaneRouteName(decodeURIComponent(match[1]))
  } catch {
    return null
  }
  return lane ? { view: 'lane-workspace', viewParams: { lane } } : null
}

export const shellPathForView = (view, viewParams = {}) =>
  view === 'lane-workspace' ? laneRoutePath(viewParams.lane) || '/' : '/'

export const shellViewForNavigation = (view, viewParams = {}) =>
  view === 'work-queue' && laneRoutePath(viewParams.lane) ? 'lane-workspace' : view

export const VIEW_META = {
  cockpit: { label: 'Cockpit', workbench: 'hermes', pinned: true },
  'work-queue': { label: 'Work Queue', workbench: 'codex' },
  'lane-workspace': { label: 'Lane Workspace', workbench: 'codex' },
  'workflow-bench': { label: 'Workflow Bench', workbench: 'hermes' },
  'message-board': { label: 'Message Board', workbench: 'hermes' },
  'skills-board': { label: 'Skills Board', workbench: 'hermes' },
  'memory-board': { label: 'Memory Board', workbench: 'hermes' },
  'prompt-library': { label: 'Prompt Library', workbench: 'codex' },
  graphify: { label: 'Graphify', workbench: 'hermes' },
  'repo-ingest': { label: 'Repo Ingest', workbench: 'codex' },
  'results-receipts': { label: 'Results & Receipts', workbench: 'hermes' },
  'tokens-roi': { label: 'Tokens & ROI', workbench: 'hermes' },
  artifacts: { label: 'Artifacts', workbench: 'codex' },
  'connections-spine': { label: 'Connections / Spine', workbench: 'hermes' },
  'mission-control': { label: 'Mission Control', workbench: 'hermes' },
  settings: { label: 'Settings / Launchers', workbench: 'hermes' },
  search: { label: 'Search', workbench: 'hermes' },
}

export const initialSessionTabs = () => [
  { id: 'cockpit', ...VIEW_META.cockpit, preview: false },
  { id: 'message-board', ...VIEW_META['message-board'], preview: true },
]

export function restoreShellSession(raw, pathname = '') {
  const fallback = { view: 'message-board', viewParams: {}, sessionTabs: initialSessionTabs() }
  let restored = fallback
  try {
    if (raw) {
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      const view = VIEW_META[parsed?.view] ? parsed.view : fallback.view
      const supplied = Array.isArray(parsed?.sessionTabs) ? parsed.sessionTabs : []
      const valid = supplied
        .filter(tab => tab && VIEW_META[tab.id])
        .slice(0, MAX_SESSION_TABS)
        .map(tab => ({ ...tab, ...VIEW_META[tab.id], params: tab.params && typeof tab.params === 'object' ? tab.params : {} }))
      const withCockpit = valid.some(tab => tab.id === 'cockpit') ? valid : [fallback.sessionTabs[0], ...valid]
      const tabs = withCockpit.some(tab => tab.id === view) ? withCockpit : openSessionTab(withCockpit, view, parsed?.viewParams || {})
      const active = tabs.find(tab => tab.id === view)
      restored = { view, viewParams: active?.params || parsed?.viewParams || {}, sessionTabs: tabs.slice(0, MAX_SESSION_TABS) }
    }
  } catch {
    restored = fallback
  }
  const route = shellRouteFromPath(pathname)
  if (!route) return restored
  const sessionTabs = openSessionTab(restored.sessionTabs, route.view, route.viewParams)
  return { ...route, sessionTabs }
}

export const shellSessionSnapshot = (view, viewParams, sessionTabs) => JSON.stringify({ view, viewParams: viewParams || {}, sessionTabs })

export const needsMeCollapseKey = (view, viewParams) => view === 'work-queue' ? viewParams?.selectedId || null : null

export function openSessionTab(tabs, id, params = {}) {
  const existing = tabs.find(tab => tab.id === id)
  if (existing) return tabs.map(tab => tab.id === id ? { ...tab, params } : tab)

  const meta = VIEW_META[id] || { label: id, workbench: 'hermes' }
  const next = { id, ...meta, params, preview: !meta.pinned }
  const previewIndex = tabs.findIndex(tab => tab.preview && !tab.pinned)
  let result = previewIndex >= 0
    ? tabs.map((tab, index) => index === previewIndex ? next : tab)
    : [...tabs, next]

  while (result.length > MAX_SESSION_TABS) {
    const removable = result.findIndex((tab, index) => index > 0 && !tab.pinned)
    if (removable < 0) break
    result = result.filter((_, index) => index !== removable)
  }
  return result
}

export const pinSessionTab = (tabs, id) => tabs.map(tab => tab.id === id ? { ...tab, pinned: true, preview: false } : tab)

export function closeSessionTab(tabs, id) {
  const target = tabs.find(tab => tab.id === id)
  if (!target || target.id === 'cockpit') return tabs
  return tabs.filter(tab => tab.id !== id)
}

export const normalizeWorkbench = value => {
  const workbench = String(value || '').toLowerCase()
  if (workbench.includes('claude')) return 'claude'
  if (workbench.includes('codex')) return 'codex'
  if (workbench.includes('hermes')) return 'hermes'
  if (workbench.includes('antigravity') || workbench === 'anti') return 'anti'
  return 'unattributed'
}

export const stateShade = status => {
  if (['agent_working', 'running'].includes(status)) return 'working'
  if (['done', 'cancelled'].includes(status)) return 'done'
  return 'queued'
}

export const workbenchColor = (workbench, status) => {
  if (['human_review', 'needs_input'].includes(status)) return 'var(--needs-review)'
  const normalized = normalizeWorkbench(workbench)
  if (normalized === 'unattributed') return 'var(--hairline)'
  return `var(--wb-${normalized}-${stateShade(status)})`
}

export const laneName = item => {
  const tag = (item?.tags || []).find(value => String(value).startsWith('lane:'))
  const lane = String(tag ? tag.split(':')[1] : item?.lane || '').toLowerCase()
  return ['marketing', 'revenue', 'delivery', 'operations'].includes(lane) ? lane : 'operations'
}

export const laneColor = lane => `var(--lane-${lane || 'operations'})`
