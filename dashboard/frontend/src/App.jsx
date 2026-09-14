import { useState, useEffect } from 'react'
import Sidebar, { MobileNav } from './components/Sidebar'
import TopBar from './components/TopBar'
import CaptureBox from './components/CaptureBox'
import Overview from './views/Overview'
import AgentWorkbench from './views/AgentWorkbench'
import PacketCreator from './views/PacketCreator'
import Tracker from './views/Tracker'
import LogsResults from './views/LogsResults'
import Connectors from './views/Connectors'
import Queue from './views/Queue'
import LaneWorkspace from './views/LaneWorkspace'
import { getDashboardCockpit, getHealth, getOverview, getQueueSummary } from './api'
import { Cockpit } from './views/DashboardV1'
import { ResultsHub, SearchHub, SystemHub } from './views/Hubs'
import { AgentsPage, MessageBoard } from './views/WorkbenchV3'
import { closeSessionTab, destinationForView, openSessionTab, pinSessionTab, restoreShellSession, shellPathForView, shellRouteFromPath, shellSessionSnapshot, shellViewForNavigation } from './shellState'
import { mergeQueueSummary, normalizeCockpitQueue, preserveQueueDataOnRefreshFailure } from './queueState'

// Every legacy sub-view now folds into one of the three hubs' local tabs
// (BUILD_SPECIFICATION "Local report/workspace tabs"). A direct deep link or
// restored session tab still lands on the right hub with the right tab open
// instead of on an orphaned standalone page.
const withTab = (Hub, tab) => props => <Hub {...props} initialFilters={{ ...(props.initialFilters || {}), tab }} />

const VIEWS = {
  'message-board': MessageBoard,
  cockpit: Cockpit,
  'work-queue': Queue,
  'lane-workspace': LaneWorkspace,
  results: ResultsHub,
  'results-receipts': withTab(ResultsHub, 'results'),
  artifacts: withTab(ResultsHub, 'artifacts'),
  search: SearchHub,
  'memory-board': withTab(SearchHub, 'memory'),
  'memory-intake': withTab(SearchHub, 'add-to-memory'),
  graphify: withTab(SearchHub, 'graphify'),
  'repo-ingest': withTab(SearchHub, 'repo-ingest'),
  system: SystemHub,
  'mission-control': withTab(SystemHub, 'watch'),
  'workflow-bench': withTab(SystemHub, 'workflows'),
  'skills-board': withTab(SystemHub, 'skills'),
  'tokens-roi': withTab(SystemHub, 'tokens'),
  'connections-spine': withTab(SystemHub, 'connections'),
  'prompt-library': withTab(SystemHub, 'prompts'),
  settings: withTab(SystemHub, 'settings'),
  overview: Overview,
  agents: AgentsPage,
  'agent-workbench': AgentWorkbench,
  packets: PacketCreator,
  tracker: Tracker,
  logs: LogsResults,
  connectors: Connectors,
  queue: Queue,
}

export default function App() {
  const [restoredShell] = useState(() => restoreShellSession(window.sessionStorage?.getItem('aos.dashboard.shell.v1'), window.location.pathname))
  const [view, setView] = useState(restoredShell.view)
  const [viewParams, setViewParams] = useState(restoredShell.viewParams)
  const [sessionTabs, setSessionTabs] = useState(restoredShell.sessionTabs)
  const [backendOk, setBackendOk] = useState(null)
  const [overview, setOverview] = useState(null)
  const [cockpit, setCockpit] = useState(null)

  const applyShellView = (nextView, params = {}) => {
    setSessionTabs(current => openSessionTab(current, nextView, params))
    setView(nextView)
    setViewParams(params)
  }

  const syncShellRoute = (nextView, params = {}, replace = false) => {
    const path = shellPathForView(nextView, params)
    const state = { ...(window.history.state || {}), aosShell: { view: nextView, viewParams: params } }
    if (replace || window.location.pathname === path) window.history.replaceState(state, '', path)
    else window.history.pushState(state, '', path)
  }

  const navigate = (nextView, params = {}) => {
    const routedView = shellViewForNavigation(nextView, params)
    applyShellView(routedView, params)
    syncShellRoute(routedView, params)
  }

  const closeTab = id => {
    const index = sessionTabs.findIndex(tab => tab.id === id)
    const nextTabs = closeSessionTab(sessionTabs, id)
    setSessionTabs(nextTabs)
    if (id === view) {
      const fallback = nextTabs[Math.min(Math.max(index - 1, 0), nextTabs.length - 1)] || nextTabs[0]
      navigate(fallback.id, fallback.params || {})
    }
  }

  const updateActiveViewParams = params => {
    const next = params || {}
    setViewParams(next)
    setSessionTabs(current => current.map(tab => tab.id === view ? { ...tab, params: next } : tab))
    syncShellRoute(view, next, true)
  }

  const refreshNeedsMe = () => getQueueSummary()
    .then(data => setCockpit(current => mergeQueueSummary(current, data)))
    .catch(() => setCockpit(current => preserveQueueDataOnRefreshFailure(current)))

  const refreshCockpit = () => {
    refreshNeedsMe()
    return getDashboardCockpit()
      .then(data => setCockpit(current => {
        const next = normalizeCockpitQueue(data)
        if (!current?.queueSummaryLoaded) return next
        return {
          ...next,
          counts: current.counts,
          needs_me: current.needs_me,
          needs_me_count: current.needs_me_count,
          human_needed_count: current.human_needed_count,
          queueSummaryLoaded: true,
        }
      }))
      .catch(() => setCockpit(current => preserveQueueDataOnRefreshFailure(current)))
  }

  useEffect(() => {
    getHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
    getOverview()
      .then(setOverview)
      .catch(() => setOverview({ error: true }))
    refreshCockpit()
    const queueSummaryPoll = window.setInterval(refreshNeedsMe, 15000)
    return () => window.clearInterval(queueSummaryPoll)
  }, [])

  useEffect(() => {
    window.sessionStorage?.setItem('aos.dashboard.shell.v1', shellSessionSnapshot(view, viewParams, sessionTabs))
  }, [view, viewParams, sessionTabs])

  useEffect(() => {
    const path = shellPathForView(restoredShell.view, restoredShell.viewParams)
    window.history.replaceState({ ...(window.history.state || {}), aosShell: { view: restoredShell.view, viewParams: restoredShell.viewParams } }, '', path)
    const onPopState = event => {
      const route = shellRouteFromPath(window.location.pathname)
      const saved = event.state?.aosShell
      if (route) applyShellView(route.view, route.viewParams)
      else if (saved && VIEWS[saved.view]) applyShellView(saved.view, saved.viewParams || {})
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    const isTypingTarget = target => {
      const tag = target?.tagName
      return target?.isContentEditable || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
    }
    const onKeyDown = event => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) return
      event.preventDefault()
      navigate('work-queue', { needsMe: true })
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const ViewComponent = VIEWS[view] || Overview
  const activeDestination = destinationForView(view)

  return (
    <div className="flex h-screen overflow-hidden bg-ink" data-testid="workbench-shell">
      <Sidebar activeDestination={activeDestination} currentView={view} onNavigate={navigate} counts={cockpit?.counts || {}} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar activeDestination={activeDestination} backendOk={backendOk} cockpit={cockpit} onNavigate={navigate} onRefresh={() => { getOverview().then(setOverview).catch(() => setOverview({ error: true })); refreshCockpit() }} />
        <CaptureBox />
        {/* Session tabs are secondary desktop-only workspace history, never
            global navigation (BUILD_SPECIFICATION "Session tabs are not
            global navigation"); on mobile the TopBar's surface title plus
            each hub's own local tabs already cover this. */}
        <div className="hidden h-10 shrink-0 items-end gap-0 overflow-x-auto border-b border-softgraph bg-graphite px-2 md:flex" role="tablist" aria-label="Session tabs" data-testid="session-tabs">
          {sessionTabs.map(tab => (
            <div
              key={tab.id}
              role="tab"
              aria-selected={view === tab.id}
              data-preview={tab.preview ? 'true' : 'false'}
              data-pinned={tab.pinned ? 'true' : 'false'}
              onDoubleClick={() => setSessionTabs(current => pinSessionTab(current, tab.id))}
              className={`group flex h-9 max-w-48 shrink-0 items-center border-x border-t border-softgraph px-2 text-xs ${view === tab.id ? 'bg-ink text-ivory' : 'bg-graphite text-taupe hover:bg-well'}`}
              style={{ borderTopColor: `var(--wb-${tab.workbench || 'hermes'}-queued)`, borderTopWidth: view === tab.id ? 3 : 2 }}
            >
              <button className="min-w-0 flex-1 truncate text-left" onClick={() => navigate(tab.id, tab.params || {})} title={tab.preview ? `${tab.label} · preview (double-click to pin)` : tab.label}>
                {tab.pinned && <span className="mr-1" aria-label="Pinned">●</span>}{tab.label}
              </button>
              {tab.id !== 'cockpit' && (
                <button onClick={() => closeTab(tab.id)} className="ml-2 rounded px-1 text-taupe opacity-70 hover:bg-well hover:text-ivory group-hover:opacity-100" aria-label={`Close ${tab.label}`}>×</button>
              )}
            </div>
          ))}
        </div>
        {/* The scroll root itself carries no padding — Queue's sticky tab bar
            depends on that to pin flush with no top gap. Page padding lives
            on the inner wrapper instead (BUILD_SPECIFICATION "Make the main
            scroll root edge-to-edge; put page padding in an inner wrapper").
            Extra bottom padding on mobile clears the fixed bottom nav. */}
        <main id="aos-main-scroll" className="flex-1 overflow-y-auto">
          <div className="p-6 pb-24 md:pb-6">
            <ViewComponent overview={overview} cockpit={cockpit} initialFilters={viewParams} onViewParamsChange={updateActiveViewParams} onNavigate={navigate} refresh={refreshCockpit} onRefresh={() => getOverview().then(setOverview).catch(() => setOverview({ error: true }))} />
          </div>
        </main>
      </div>
      <MobileNav activeDestination={activeDestination} onNavigate={navigate} counts={cockpit?.counts || {}} />
    </div>
  )
}
