import { useState, useEffect } from 'react'
import { ScrollText, FolderOpen, RefreshCw, FileText } from 'lucide-react'
import { getLogs, getResults, getPackets } from '../api'

const EmptyState = ({ label }) => (
  <div className="text-center py-12">
    <FileText size={28} className="text-softgraph mx-auto mb-3" />
    <div className="text-sm text-taupe font-mono">No {label} yet</div>
    <div className="text-xs text-taupe/60 mt-1">Files placed in /{label}/ will appear here</div>
  </div>
)

const FileEntry = ({ name, content, modified }) => {
  const [open, setOpen] = useState(false)
  const ts = new Date(modified).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
  return (
    <div className="border border-softgraph rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-graphite hover:bg-softgraph/50 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <FileText size={12} className="text-taupe flex-shrink-0" />
          <span className="text-sm text-stone font-mono">{name}</span>
        </div>
        <span className="text-xs text-taupe font-mono">{ts}</span>
      </button>
      {open && (
        <div className="bg-ink border-t border-softgraph px-4 py-3 max-h-64 overflow-y-auto">
          <pre className="text-xs font-mono text-stone whitespace-pre-wrap leading-relaxed">{content || '(empty)'}</pre>
        </div>
      )}
    </div>
  )
}

export default function LogsResults() {
  const [tab, setTab] = useState('logs')
  const [packets, setPackets] = useState(null)
  const [logs, setLogs] = useState(null)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [p, l, r] = await Promise.all([getPackets(), getLogs(), getResults()])
      setPackets(p.packets)
      setLogs(l.logs)
      setResults(r.results)
    } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const items = tab === 'packets' ? packets : tab === 'logs' ? logs : results
  const label = tab === 'packets' ? 'packets' : tab === 'logs' ? 'logs' : 'results'

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ivory mb-1">Logs & Results</h1>
          <p className="text-sm text-taupe">Read-only view of /packets/, /logs/, and /results/ folders.</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono bg-softgraph text-taupe hover:text-stone transition-colors"
        >
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="flex gap-2">
        {[
          { id: 'packets', label: 'Packets', icon: FileText, count: packets },
          { id: 'logs', label: 'Logs', icon: ScrollText, count: logs },
          { id: 'results', label: 'Results', icon: FolderOpen, count: results },
        ].map(({ id, label: lbl, icon: TabIcon, count }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-colors ${
              tab === id
                ? 'bg-champagne text-ink'
                : 'bg-graphite text-taupe hover:text-stone border border-softgraph'
            }`}
          >
            <TabIcon size={13} />
            {lbl}
            {count !== null && (
              <span className={`text-xs font-mono ml-1 ${tab === id ? 'text-ink/70' : 'text-taupe'}`}>
                {count.length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {loading && <div className="text-xs text-taupe font-mono py-8 text-center">Loading…</div>}
        {!loading && items !== null && items.length === 0 && <EmptyState label={label} />}
        {!loading && items !== null && items.map(item => (
          <FileEntry key={item.name} {...item} />
        ))}
        {!loading && items === null && (
          <div className="text-xs text-taupe font-mono text-center py-8">
            Could not load {label} — backend may be offline
          </div>
        )}
      </div>

      <div className="bg-graphite border border-softgraph rounded-lg p-4 text-xs text-taupe font-mono space-y-1">
        <div>Packets path: Agentic OS Live/packets/</div>
        <div>Logs path: Agentic OS Live/logs/</div>
        <div>Results path: Agentic OS Live/results/</div>
        <div className="text-taupe/60 pt-1">This view is read-only. No files are modified, imported, or synced.</div>
      </div>
    </div>
  )
}
