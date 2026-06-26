import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8010'

export default function Connectors() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [refreshOutput, setRefreshOutput] = useState('')

  async function loadStatus() {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/connectors/status`)
      if (!res.ok) throw new Error(`Status request failed: ${res.status}`)
      const data = await res.json()
      setStatus(data)
    } catch (err) {
      setError(err.message || String(err))
    } finally {
      setLoading(false)
    }
  }

  async function refreshComposio() {
    setRefreshing(true)
    setError('')
    setRefreshOutput('')
    try {
      const res = await fetch(`${API_BASE}/api/connectors/composio/refresh`, { method: 'POST' })
      if (!res.ok) throw new Error(`Refresh failed: ${res.status}`)
      const data = await res.json()
      setRefreshOutput(data.output || JSON.stringify(data, null, 2))
      await loadStatus()
    } catch (err) {
      setError(err.message || String(err))
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const connectors = Array.isArray(status?.connectors) ? status.connectors : []

  return (
    <main className="min-h-screen bg-[#111315] px-6 py-8 text-[#F7F3EA]">
      <section className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border border-[#2B2F32] bg-[#0D1418] p-6 shadow-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-[#B89B63]">Agentic OS</p>
              <h1 className="mt-2 text-3xl font-semibold">Connectors</h1>
              <p className="mt-2 max-w-3xl text-sm text-[#D8D0C2]">
                Local connector status. Read/search/status/draft/prepare by default.
                Send/write/push/mutate only when explicitly commanded.
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={loadStatus}
                className="rounded-xl border border-[#4E5A50] px-4 py-2 text-sm text-[#F7F3EA] hover:border-[#B89B63]"
              >
                Reload Local Status
              </button>

              <button
                type="button"
                onClick={refreshComposio}
                disabled={refreshing}
                className="rounded-xl bg-[#B89B63] px-4 py-2 text-sm font-semibold text-[#111315] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {refreshing ? 'Refreshing…' : 'Refresh Composio CLI Status'}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-3 text-sm md:grid-cols-3">
            <div className="rounded-2xl border border-[#2B2F32] bg-[#111315] p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-[#7A746A]">Updated</div>
              <div className="mt-1 text-[#F7F3EA]">{status?.updated || 'Loading…'}</div>
            </div>
            <div className="rounded-2xl border border-[#2B2F32] bg-[#111315] p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-[#7A746A]">Mode</div>
              <div className="mt-1 text-[#F7F3EA]">{status?.mode || 'Local connector status'}</div>
            </div>
            <div className="rounded-2xl border border-[#2B2F32] bg-[#111315] p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-[#7A746A]">Composio CLI</div>
              <div className="mt-1 text-[#F7F3EA]">{status?.composio_cli?.status || 'Not loaded'}</div>
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-[#A56C53] bg-[#1b1110] p-4 text-sm text-[#F7F3EA]">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-3xl border border-[#2B2F32] bg-[#0D1418] p-6 text-[#D8D0C2]">
            Loading connector status…
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {connectors.map((connector) => (
              <article
                key={connector.name}
                className="rounded-3xl border border-[#2B2F32] bg-[#0D1418] p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-lg font-semibold">{connector.name}</h2>
                  <span className="rounded-full border border-[#4E5A50] px-3 py-1 text-xs text-[#D8D0C2]">
                    {connector.status}
                  </span>
                </div>
                <p className="mt-4 text-xs uppercase tracking-[0.2em] text-[#7A746A]">Current path</p>
                <p className="mt-1 break-words font-mono text-xs text-[#D8D0C2]">
                  {connector.current_path || connector.current_path_or_connection || '—'}
                </p>
                <p className="mt-4 text-xs uppercase tracking-[0.2em] text-[#7A746A]">Action policy</p>
                <p className="mt-1 text-sm text-[#F7F3EA]">{connector.action_policy || '—'}</p>
              </article>
            ))}
          </div>
        )}

        {refreshOutput && (
          <section className="rounded-3xl border border-[#2B2F32] bg-[#0D1418] p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Latest Composio CLI Refresh</h2>
              <span className="text-xs text-[#7A746A]">connectors/composio_live_connections.txt</span>
            </div>
            <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-2xl bg-[#111315] p-4 font-mono text-xs text-[#D8D0C2]">
              {refreshOutput}
            </pre>
          </section>
        )}
      </section>
    </main>
  )
}
