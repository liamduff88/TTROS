export const MAX_SESSION_TABS = 8

export const VIEW_META = {
  cockpit: { label: 'Cockpit', workbench: 'hermes', pinned: true },
  'work-queue': { label: 'Work Queue', workbench: 'codex' },
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

export function restoreShellSession(raw) {
  const fallback = { view: 'message-board', viewParams: {}, sessionTabs: initialSessionTabs() }
  if (!raw) return fallback
  try {
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
    return { view, viewParams: active?.params || parsed?.viewParams || {}, sessionTabs: tabs.slice(0, MAX_SESSION_TABS) }
  } catch {
    return fallback
  }
}

export const shellSessionSnapshot = (view, viewParams, sessionTabs) => JSON.stringify({ view, viewParams: viewParams || {}, sessionTabs })

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
  return 'hermes'
}

export const stateShade = status => {
  if (['agent_working', 'running'].includes(status)) return 'working'
  if (['done', 'cancelled'].includes(status)) return 'done'
  return 'queued'
}

export const workbenchColor = (workbench, status) => {
  if (['human_review', 'needs_input'].includes(status)) return 'var(--needs-review)'
  return `var(--wb-${normalizeWorkbench(workbench)}-${stateShade(status)})`
}

export const laneName = item => {
  const tag = (item?.tags || []).find(value => String(value).startsWith('lane:'))
  const lane = String(tag ? tag.split(':')[1] : item?.lane || '').toLowerCase()
  return ['marketing', 'revenue', 'delivery', 'operations'].includes(lane) ? lane : 'operations'
}

export const laneColor = lane => `var(--lane-${lane || 'operations'})`
