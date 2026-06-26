import { Circle, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { getOverview } from '../api'

export default function TopBar({ backendOk, overview }) {
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 600)
  }

  const now = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

  return (
    <header className="flex items-center justify-between px-6 py-3 bg-graphite border-b border-softgraph flex-shrink-0">
      <div className="flex items-center gap-6">
        <div className="text-xs text-taupe font-mono">{new Date().toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })} · {now}</div>
        <div className="flex items-center gap-1.5">
          <Circle
            size={7}
            className={backendOk === null ? 'text-taupe fill-taupe' : backendOk ? 'text-olive fill-olive' : 'text-clay fill-clay'}
          />
          <span className="text-xs font-mono text-taupe">
            {backendOk === null ? 'Connecting…' : backendOk ? 'API online' : 'API offline — start backend'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {overview && (
          <div className="flex items-center gap-5 text-xs font-mono">
            <span className="text-taupe">Packets <span className="text-stone ml-1">{overview.totalPackets}</span></span>
            <span className="text-taupe">Logs <span className="text-stone ml-1">{overview.totalLogs}</span></span>
            <span className="text-taupe">Results <span className="text-stone ml-1">{overview.totalResults}</span></span>
            {overview.estimatedValue > 0 && (
              <span className="text-taupe">Value <span className="text-champagne ml-1">${overview.estimatedValue.toLocaleString()}</span></span>
            )}
          </div>
        )}
        <button
          onClick={handleRefresh}
          className="text-taupe hover:text-stone transition-colors"
          title="Refresh overview"
        >
          <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>
    </header>
  )
}
