import { useState } from 'react'
import { HubTabs } from '../components/DashboardKit'
import { ResultsReceipts, ConnectionsSpine, PromptLibrary, GraphifyPage, RepoIngest, SettingsLaunchers, WorkflowBench, SkillsBoard, TokensROI, MemoryBoard } from './DashboardV1'
import { ArtifactsPage, MissionControl, SearchPage } from './WorkbenchV3'
import MemoryIntake from './MemoryIntake'

// Shared local-tab container for the Results, Search, and System destinations
// (BUILD_SPECIFICATION "Local report/workspace tabs"). The active tab is
// persisted through the same viewParams/session mechanism every other view
// already uses, so it survives refresh, popstate, and re-navigation.
function Hub({ tabs, initialFilters, onViewParamsChange, ...rest }) {
  const requested = initialFilters?.tab
  const [active, setActive] = useState(tabs.some(tab => tab.id === requested) ? requested : tabs[0].id)
  const change = id => {
    setActive(id)
    onViewParamsChange?.({ ...initialFilters, tab: id })
  }
  const current = tabs.find(tab => tab.id === active) || tabs[0]
  const ActiveComponent = current.component
  return (
    <>
      <HubTabs tabs={tabs} active={current.id} onChange={change} />
      <ActiveComponent {...rest} initialFilters={initialFilters} />
    </>
  )
}

// Results owns Recent Results | Artifacts | Receipts (BUILD_SPECIFICATION
// "Components/files"). Recent Results and Receipts both read the existing
// results/receipts feed; Artifacts reuses the existing indexed artifact
// library. No new backend route.
export function ResultsHub(props) {
  const tabs = [
    { id: 'results', label: 'Recent Results', component: ResultsReceipts },
    { id: 'artifacts', label: 'Artifacts', component: ArtifactsPage },
    { id: 'receipts', label: 'Receipts', component: ResultsReceipts },
  ]
  return <Hub tabs={tabs} {...props} />
}

// Search owns Search | Memory | Graphify | Add to Memory. Repo Ingest folds
// in here too (existing shellState VIEW_DESTINATION mapping) since it is
// also a Business Brain ingestion path, not a separate product.
export function SearchHub(props) {
  const tabs = [
    { id: 'search', label: 'Search', component: SearchPage },
    { id: 'memory', label: 'Memory', component: MemoryBoard },
    { id: 'graphify', label: 'Graphify', component: GraphifyPage },
    { id: 'add-to-memory', label: 'Add to Memory', component: MemoryIntake },
    { id: 'repo-ingest', label: 'Repo Ingest', component: RepoIngest },
  ]
  return <Hub tabs={tabs} {...props} />
}

// System owns System Watch | Connections | Workflows/Skills | Tokens |
// Settings. Tab ids match the existing onNavigate('system', { tab }) call
// sites in DashboardKit/TopBar ('watch', 'tokens') so those deep links keep
// landing on the right tab.
export function SystemHub(props) {
  const tabs = [
    { id: 'watch', label: 'System Watch', component: MissionControl },
    { id: 'connections', label: 'Connections', component: ConnectionsSpine },
    { id: 'workflows', label: 'Workflows', component: WorkflowBench },
    { id: 'skills', label: 'Skills', component: SkillsBoard },
    { id: 'tokens', label: 'Tokens', component: TokensROI },
    { id: 'settings', label: 'Settings', component: SettingsLaunchers },
    { id: 'prompts', label: 'Prompts', component: PromptLibrary },
  ]
  return <Hub tabs={tabs} {...props} />
}
