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
import { getDashboardCockpit, getHealth, getOverview } from './api'
import { Cockpit, ConnectionsSpine, GraphifyPage, MemoryBoard, PromptLibrary, RepoIngest, ResultsReceipts, SettingsLaunchers, SkillsBoard, TokensROI, WorkflowBench } from './views/DashboardV1'
import { ArtifactsPage, AgentsPage, MessageBoard, MissionControl } from './views/WorkbenchV3'
import { NeedsMeRail } from './components/DashboardKit'

const VIEWS = {
  'message-board': MessageBoard,
  cockpit: Cockpit,
  'work-queue': Queue,
  artifacts: ArtifactsPage,
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
  const [view, setView] = useState('message-board')
  const [viewParams, setViewParams] = useState({})
  const [backendOk, setBackendOk] = useState(null)
  const [overview, setOverview] = useState(null)
  const [cockpit, setCockpit] = useState(null)

  const navigate = (nextView, params = {}) => {
    setView(nextView)
    setViewParams(params)
  }

  const refreshCockpit = () => getDashboardCockpit().then(setCockpit).catch(() => setCockpit({ error: true }))

  useEffect(() => {
    getHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
    getOverview()
      .then(setOverview)
      .catch(() => setOverview({ error: true }))
    refreshCockpit()
  }, [])

  const ViewComponent = VIEWS[view] || Overview

  return (
    <div className="flex h-screen overflow-hidden bg-ink">
      <Sidebar activeView={view} onNavigate={navigate} counts={cockpit?.counts || {}} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar backendOk={backendOk} overview={overview} cockpit={cockpit} onNavigate={navigate} onRefresh={() => { getOverview().then(setOverview).catch(() => setOverview({ error: true })); refreshCockpit() }} />
        <div className="flex min-h-0 flex-1">
          <main className="flex-1 overflow-y-auto p-6">
            <ViewComponent overview={overview} cockpit={cockpit} initialFilters={viewParams} onNavigate={navigate} refresh={refreshCockpit} onRefresh={() => getOverview().then(setOverview).catch(() => setOverview({ error: true }))} />
          </main>
          <NeedsMeRail cockpit={cockpit} onNavigate={navigate} />
        </div>
      </div>
    </div>
  )
}
