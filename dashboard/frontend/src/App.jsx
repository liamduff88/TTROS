import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import Overview from './views/Overview'
import AgentWorkbench from './views/AgentWorkbench'
import PacketCreator from './views/PacketCreator'
import Tracker from './views/Tracker'
import LogsResults from './views/LogsResults'
import Connectors from './views/Connectors'
import { getHealth, getOverview } from './api'

const VIEWS = {
  overview: Overview,
  agents: AgentWorkbench,
  packets: PacketCreator,
  tracker: Tracker,
  logs: LogsResults,
  connectors: Connectors,
}

export default function App() {
  const [view, setView] = useState('overview')
  const [backendOk, setBackendOk] = useState(null)
  const [overview, setOverview] = useState(null)

  useEffect(() => {
    getHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
    getOverview()
      .then(setOverview)
      .catch(() => setOverview({ error: true }))
  }, [])

  const ViewComponent = VIEWS[view] || Overview

  return (
    <div className="flex h-screen overflow-hidden bg-ink">
      <Sidebar activeView={view} onNavigate={setView} />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar backendOk={backendOk} overview={overview} />
        <main className="flex-1 overflow-y-auto p-6">
          <ViewComponent overview={overview} onNavigate={setView} onRefresh={() => getOverview().then(setOverview).catch(() => setOverview({ error: true }))} />
        </main>
      </div>
    </div>
  )
}
