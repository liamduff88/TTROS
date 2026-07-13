import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FilePenLine,
  Inbox,
  Loader2,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Signal,
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8010'

const ACTION_PRESETS = [
  {
    id: 'mail-read',
    title: 'Read latest mail',
    description: 'Fetch a small inbox sample without sending or changing mail.',
    icon: Inbox,
    intent: 'read',
    toolSlug: 'GMAIL_FETCH_EMAILS',
    jsonArgs: { max_results: 5 },
  },
  {
    id: 'mail-search',
    title: 'Search mail',
    description: 'Search recent mail with an editable query and result cap.',
    icon: Search,
    intent: 'search',
    toolSlug: 'GMAIL_SEARCH_EMAILS',
    jsonArgs: { query: 'newer_than:7d', max_results: 10 },
  },
  {
    id: 'status-check',
    title: 'Connector status',
    description: 'Run an adapter-backed status style lookup for a known tool.',
    icon: Signal,
    intent: 'status',
    toolSlug: 'GMAIL_FETCH_EMAILS',
    jsonArgs: { max_results: 1 },
  },
  {
    id: 'draft-mail',
    title: 'Prepare draft',
    description: 'Create a draft only after explicit operator write intent.',
    icon: FilePenLine,
    intent: 'draft',
    requiresIntent: true,
    toolSlug: 'GMAIL_CREATE_EMAIL_DRAFT',
    jsonArgs: {
      recipient_email: 'recipient@example.com',
      subject: 'Draft subject',
      body: 'Draft body prepared by operator request.',
    },
  },
]

function formatJson(value) {
  return JSON.stringify(value, null, 2)
}

function normalizeJsonError(message) {
  if (!message) return 'Invalid JSON payload'
  return message.replace(/^JSON\.parse: /i, '')
}

export default function Connectors() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [refreshOutput, setRefreshOutput] = useState('')
  const [selectedPresetId, setSelectedPresetId] = useState(ACTION_PRESETS[0].id)
  const [toolSlug, setToolSlug] = useState(ACTION_PRESETS[0].toolSlug)
  const [payloadText, setPayloadText] = useState(formatJson(ACTION_PRESETS[0].jsonArgs))
  const [operatorIntent, setOperatorIntent] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState('')
  const [actionResponse, setActionResponse] = useState(null)

  const selectedPreset = useMemo(
    () => ACTION_PRESETS.find((preset) => preset.id === selectedPresetId) || ACTION_PRESETS[0],
    [selectedPresetId],
  )

  const parsedPayload = useMemo(() => {
    try {
      const parsed = JSON.parse(payloadText)
      return { ok: parsed && typeof parsed === 'object' && !Array.isArray(parsed), value: parsed }
    } catch (err) {
      return { ok: false, error: normalizeJsonError(err.message) }
    }
  }, [payloadText])

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

  function selectPreset(preset) {
    setSelectedPresetId(preset.id)
    setToolSlug(preset.toolSlug)
    setPayloadText(formatJson(preset.jsonArgs))
    setOperatorIntent(false)
    setActionError('')
  }

  async function runAction() {
    const cleanToolSlug = toolSlug.trim()
    setActionError('')
    setActionResponse(null)

    if (!cleanToolSlug) {
      setActionError('Tool slug is required.')
      return
    }

    if (!parsedPayload.ok) {
      setActionError(`Payload must be a JSON object: ${parsedPayload.error || 'invalid JSON'}`)
      return
    }

    if (selectedPreset.requiresIntent && !operatorIntent) {
      setActionError('This preset can write external state. Confirm explicit operator intent first.')
      return
    }

    setActionLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/connectors/composio/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_slug: cleanToolSlug, json_args: parsedPayload.value }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail || `Action request failed: ${res.status}`)
      setActionResponse(data)
    } catch (err) {
      setActionError(err.message || String(err))
    } finally {
      setActionLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const connectors = Array.isArray(status?.connectors) ? status.connectors : []
  const actionBlocked = actionLoading || !parsedPayload.ok || (selectedPreset.requiresIntent && !operatorIntent)

  return (
    <div className="min-h-full bg-[var(--surface-1)] px-6 py-8 text-[var(--text)]">
      <section className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border border-[var(--hairline)] bg-[var(--surface-0)] p-6 shadow-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-[var(--wb-hermes-queued)]">Agentic OS</p>
              <h1 className="mt-2 text-3xl font-semibold">Connector Controls</h1>
              <p className="mt-2 max-w-3xl text-sm text-[var(--text-dim)]">
                Cockpit actions use the existing Composio route into clean WSL AgenticOSClean.
                Read, search, status, and draft preparation stay visible here; external sends,
                writes, and pushes require explicit operator intent.
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={loadStatus}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--lane-marketing)] px-4 py-2 text-sm text-[var(--text)] hover:border-[var(--wb-hermes-queued)]"
              >
                <RefreshCw size={15} />
                Reload Status
              </button>

              <button
                type="button"
                onClick={refreshComposio}
                disabled={refreshing}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--wb-hermes-queued)] px-4 py-2 text-sm font-semibold text-[var(--text)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {refreshing ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                {refreshing ? 'Refreshing...' : 'Refresh CLI Status'}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-3 text-sm md:grid-cols-3">
            <div className="rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">Updated</div>
              <div className="mt-1 text-[var(--text)]">{status?.updated || 'Loading...'}</div>
            </div>
            <div className="rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">Route</div>
              <div className="mt-1 font-mono text-xs text-[var(--text)]">POST /api/connectors/composio/action</div>
            </div>
            <div className="rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">Composio CLI</div>
              <div className="mt-1 text-[var(--text)]">{status?.composio_cli?.status || 'Not loaded'}</div>
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-[var(--wb-claude-working)] bg-[var(--surface-2)] p-4 text-sm text-[var(--text)]">
            {error}
          </div>
        )}

        <section className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-3xl border border-[var(--hairline)] bg-[var(--surface-0)] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--wb-hermes-queued)]">Quick actions</p>
                <h2 className="mt-1 text-xl font-semibold">Composio Operator Panel</h2>
              </div>
              <span className="rounded-full border border-[var(--lane-marketing)] px-3 py-1 text-xs text-[var(--text-dim)]">
                PowerShell fallback
              </span>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {ACTION_PRESETS.map((preset) => {
                const Icon = preset.icon
                const active = selectedPresetId === preset.id
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => selectPreset(preset)}
                    className={`min-h-[132px] rounded-2xl border p-4 text-left transition ${
                      active
                        ? 'border-[var(--wb-hermes-queued)] bg-[var(--surface-2)]'
                        : 'border-[var(--hairline)] bg-[var(--surface-1)] hover:border-[var(--lane-marketing)]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--hairline)] text-[var(--wb-hermes-queued)]">
                        <Icon size={18} />
                      </div>
                      <span className="rounded-full border border-[var(--lane-marketing)] px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] text-[var(--text-dim)]">
                        {preset.intent}
                      </span>
                    </div>
                    <h3 className="mt-4 text-base font-semibold text-[var(--text)]">{preset.title}</h3>
                    <p className="mt-2 text-sm leading-5 text-[var(--text-dim)]">{preset.description}</p>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="rounded-3xl border border-[var(--hairline)] bg-[var(--surface-0)] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[var(--wb-hermes-queued)]">Payload</p>
                <h2 className="mt-1 text-xl font-semibold">Action Request</h2>
              </div>
              <span className="rounded-full border border-[var(--hairline)] px-3 py-1 font-mono text-xs text-[var(--text-dim)]">
                {selectedPreset.intent}
              </span>
            </div>

            <label className="mt-5 block text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]" htmlFor="tool-slug">
              Tool slug
            </label>
            <input
              id="tool-slug"
              value={toolSlug}
              onChange={(event) => setToolSlug(event.target.value)}
              className="mt-2 w-full rounded-xl border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2 font-mono text-sm text-[var(--text)] outline-none focus:border-[var(--wb-hermes-queued)]"
              spellCheck="false"
            />

            <label className="mt-4 block text-xs uppercase tracking-[0.18em] text-[var(--text-dim)]" htmlFor="payload-json">
              JSON args
            </label>
            <textarea
              id="payload-json"
              value={payloadText}
              onChange={(event) => setPayloadText(event.target.value)}
              className="mt-2 min-h-[190px] w-full resize-y rounded-xl border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-3 font-mono text-xs leading-5 text-[var(--text)] outline-none focus:border-[var(--wb-hermes-queued)]"
              spellCheck="false"
            />

            {!parsedPayload.ok && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-[var(--wb-claude-working)] bg-[var(--surface-2)] p-3 text-sm text-[var(--text)]">
                <AlertTriangle size={16} className="mt-0.5 flex-shrink-0 text-[var(--wb-claude-working)]" />
                <span>Payload must be a JSON object: {parsedPayload.error}</span>
              </div>
            )}

            <label className="mt-4 flex items-start gap-3 rounded-xl border border-[var(--hairline)] bg-[var(--surface-1)] p-3 text-sm text-[var(--text-dim)]">
              <input
                type="checkbox"
                checked={operatorIntent}
                onChange={(event) => setOperatorIntent(event.target.checked)}
                className="mt-1 h-4 w-4 accent-[var(--wb-hermes-queued)]"
              />
              <span>
                I explicitly intend this action if it sends, writes, drafts, pushes, or mutates
                external connector state.
              </span>
            </label>

            <button
              type="button"
              onClick={runAction}
              disabled={actionBlocked}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--wb-hermes-queued)] px-4 py-3 text-sm font-semibold text-[var(--text)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {actionLoading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {actionLoading ? 'Running action...' : 'Run Selected Action'}
            </button>
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
          <div className="rounded-3xl border border-[var(--hairline)] bg-[var(--surface-0)] p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Connector Status</h2>
              <span className="text-xs text-[var(--text-dim)]">{connectors.length} local records</span>
            </div>

            {loading ? (
              <div className="rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-sm text-[var(--text-dim)]">
                Loading connector status...
              </div>
            ) : connectors.length ? (
              <div className="grid gap-3">
                {connectors.map((connector) => (
                  <article key={connector.name} className="rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-base font-semibold">{connector.name}</h3>
                      <span className="rounded-full border border-[var(--lane-marketing)] px-3 py-1 text-xs text-[var(--text-dim)]">
                        {connector.status}
                      </span>
                    </div>
                    <p className="mt-3 text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">Current path</p>
                    <p className="mt-1 break-words font-mono text-xs text-[var(--text-dim)]">
                      {connector.current_path || connector.current_path_or_connection || '-'}
                    </p>
                    <p className="mt-3 text-xs uppercase tracking-[0.2em] text-[var(--text-dim)]">Policy</p>
                    <p className="mt-1 text-sm text-[var(--text)]">{connector.action_policy || '-'}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-sm text-[var(--text-dim)]">
                No connector status records returned.
              </div>
            )}
          </div>

          <div className="rounded-3xl border border-[var(--hairline)] bg-[var(--surface-0)] p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Response Preview</h2>
              {actionResponse?.ok ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--lane-marketing)] px-3 py-1 text-xs text-[var(--text-dim)]">
                  <CheckCircle2 size={13} className="text-[var(--wb-hermes-queued)]" />
                  OK
                </span>
              ) : (
                <span className="rounded-full border border-[var(--hairline)] px-3 py-1 text-xs text-[var(--text-dim)]">
                  Awaiting action
                </span>
              )}
            </div>

            {actionLoading ? (
              <div className="flex min-h-[260px] items-center justify-center rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] text-sm text-[var(--text-dim)]">
                <Loader2 size={18} className="mr-2 animate-spin text-[var(--wb-hermes-queued)]" />
                Waiting for shared adapter response...
              </div>
            ) : actionError ? (
              <div className="min-h-[260px] rounded-2xl border border-[var(--wb-claude-working)] bg-[var(--surface-2)] p-4 text-sm text-[var(--text)]">
                {actionError}
              </div>
            ) : actionResponse ? (
              <pre className="max-h-[520px] min-h-[260px] overflow-auto whitespace-pre-wrap rounded-2xl bg-[var(--surface-1)] p-4 font-mono text-xs text-[var(--text-dim)]">
                {formatJson(actionResponse)}
              </pre>
            ) : (
              <div className="min-h-[260px] rounded-2xl border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-sm text-[var(--text-dim)]">
                No connector action has been run from this panel.
              </div>
            )}
          </div>
        </section>

        {refreshOutput && (
          <section className="rounded-3xl border border-[var(--hairline)] bg-[var(--surface-0)] p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Latest Composio CLI Refresh</h2>
              <span className="text-xs text-[var(--text-dim)]">connectors/composio_live_connections.txt</span>
            </div>
            <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-2xl bg-[var(--surface-1)] p-4 font-mono text-xs text-[var(--text-dim)]">
              {refreshOutput}
            </pre>
          </section>
        )}
      </section>
    </div>
  )
}
