import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import Overview from './views/Overview'
import AgentWorkbench from './views/AgentWorkbench'
import PacketCreator from './views/PacketCreator'
import Tracker from './views/Tracker'
import LogsResults from './views/LogsResults'
import Connectors from './views/Connectors'
import Queue from './views/Queue'
import { getDashboardCockpit, getHealth, getOverview, getQueueSummary } from './api'
import { Cockpit, ConnectionsSpine, GraphifyPage, MemoryBoard, PromptLibrary, RepoIngest, ResultsReceipts, SettingsLaunchers, SkillsBoard, TokensROI, WorkflowBench } from './views/DashboardV1'
import { ArtifactsPage, AgentsPage, MessageBoard, MissionControl, SearchPage } from './views/WorkbenchV3'
import { NeedsMeRail } from './components/DashboardKit'
import { closeSessionTab, openSessionTab, pinSessionTab, restoreShellSession, shellSessionSnapshot } from './shellState'
import { mergeQueueSummary, normalizeCockpitQueue } from './queueState'

const VIEWS = {
  'message-board': MessageBoard,
  cockpit: Cockpit,
  'work-queue': Queue,
  artifacts: ArtifactsPage,
  search: SearchPage,
  'mission-control': MissionControl,
  'workflow-bench': WorkflowBench,
  'skills-board': SkillsBoard,
  'memory-board': MemoryBoard,
  graphify: GraphifyPage,
  'repo-ingest': RepoIngest,
  'results-receipts': ResultsReceipts,
  'tokens-roi': TokensROI,
  'connections-spine': ConnectionsSpine,
  'prompt-library': PromptLibrary,
  settings: SettingsLaunchers,
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
  const [restoredShell] = useState(() => restoreShellSession(window.sessionStorage?.getItem('aos.dashboard.shell.v1')))
  const [view, setView] = useState(restoredShell.view)
  const [viewParams, setViewParams] = useState(restoredShell.viewParams)
  const [sessionTabs, setSessionTabs] = useState(restoredShell.sessionTabs)
  const [backendOk, setBackendOk] = useState(null)
  const [overview, setOverview] = useState(null)
  const [cockpit, setCockpit] = useState(null)

  const navigate = (nextView, params = {}) => {
    setSessionTabs(current => openSessionTab(current, nextView, params))
    setView(nextView)
    setViewParams(params)
  }

  const closeTab = id => {
    const index = sessionTabs.findIndex(tab => tab.id === id)
    const nextTabs = closeSessionTab(sessionTabs, id)
    setSessionTabs(nextTabs)
    if (id === view) {
      const fallback = nextTabs[Math.min(Math.max(index - 1, 0), nextTabs.length - 1)] || nextTabs[0]
      setView(fallback.id)
      setViewParams(fallback.params || {})
    }
  }

  const updateActiveViewParams = params => {
    const next = params || {}
    setViewParams(next)
    setSessionTabs(current => current.map(tab => tab.id === view ? { ...tab, params: next } : tab))
  }

  const refreshNeedsMe = () => getQueueSummary()
    .then(data => setCockpit(current => mergeQueueSummary(current, data)))
    .catch(() => setCockpit(current => current ? { ...current, refreshError: true } : { error: true }))

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
      .catch(() => setCockpit(current => current ? { ...current, refreshError: true } : { error: true }))
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

  const ViewComponent = VIEWS[view] || Overview

  return (
    <div className="flex h-screen overflow-hidden bg-ink" data-testid="workbench-shell">
      <Sidebar activeView={view} onNavigate={navigate} counts={cockpit?.counts || {}} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar backendOk={backendOk} overview={overview} cockpit={cockpit} onNavigate={navigate} onRefresh={() => { getOverview().then(setOverview).catch(() => setOverview({ error: true })); refreshCockpit() }} />
        <div className="flex h-10 shrink-0 items-end gap-0 overflow-x-auto border-b border-softgraph bg-graphite px-2" role="tablist" aria-label="Session tabs" data-testid="session-tabs">
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
        <div className="flex min-h-0 flex-1">
          <main className="flex-1 overflow-y-auto p-6">
            <ViewComponent overview={overview} cockpit={cockpit} initialFilters={viewParams} onViewParamsChange={updateActiveViewParams} onNavigate={navigate} refresh={refreshCockpit} onRefresh={() => getOverview().then(setOverview).catch(() => setOverview({ error: true }))} />
          </main>
          <NeedsMeRail cockpit={cockpit} onNavigate={navigate} />
        </div>
      </div>
    </div>
  )
}
