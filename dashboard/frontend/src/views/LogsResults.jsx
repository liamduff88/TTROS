import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileText,
  FolderOpen,
  ListFilter,
  RefreshCw,
  ScrollText,
  Search,
  TerminalSquare,
} from 'lucide-react'
import { getLogs, getResults, getPackets } from '../api'

const SECTION_CONFIG = {
  all: { label: 'All history', icon: Clock3 },
  results: { label: 'Results', icon: FolderOpen },
  logs: { label: 'Logs', icon: ScrollText },
  runs: { label: 'Agent runs', icon: TerminalSquare },
  attention: { label: 'Needs attention', icon: AlertTriangle },
}

const SOURCE_META = {
  result: { label: 'Result', icon: FolderOpen, tone: 'text-champagne' },
  log: { label: 'Log', icon: ScrollText, tone: 'text-stone' },
  packet: { label: 'Agent run', icon: TerminalSquare, tone: 'text-olive' },
}

const ATTENTION_PATTERN = /\b(error|failed|failure|exception|traceback|needs attention|blocked|denied|unauthorized|timeout)\b/i
const ATTENTION_MATCHERS = [
  { label: 'UnicodeDecodeError found', pattern: /UnicodeDecodeError/i },
  { label: 'Traceback found', pattern: /Traceback \(most recent call last\)|\btraceback\b/i },
  { label: 'URLError found', pattern: /\bURLError\b/i },
  { label: 'TimeoutError found', pattern: /\bTimeoutError\b/i },
  { label: 'Timeout found', pattern: /\btimeout\b/i },
  { label: 'Exception found', pattern: /\bexception\b/i },
  { label: 'Failure found', pattern: /\bfailed\b|\bfailure\b/i },
  { label: 'Blocked found', pattern: /\bblocked\b/i },
  { label: 'Denied found', pattern: /\bdenied\b|\bunauthorized\b/i },
  { label: 'Error found', pattern: /\berror\b/i },
  { label: 'Needs attention', pattern: /needs attention/i },
]
const SECRET_LINE_PATTERN = /(secret|token|api[_-]?key|oauth|password|credential|chat[_-]?id|authorization|bearer)/i
const MAX_PREVIEW_CHARS = 12000
const STALE_ATTENTION_MS = 24 * 60 * 60 * 1000

const formatTime = value => {
  if (!value) return 'No timestamp'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown time'
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const parseContent = content => {
  if (!content || typeof content !== 'string') return null
  try {
    return JSON.parse(content)
  } catch {
    return null
  }
}

const sanitizeLine = line => (SECRET_LINE_PATTERN.test(line) ? '[redacted sensitive line]' : line.trim())

const parseLineTimestamp = line => {
  const match = String(line || '').match(/\b(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}(?::\d{2})?))?/)
  if (!match) return null
  const candidate = match[2] ? `${match[1]}T${match[2]}` : match[1]
  const parsed = new Date(candidate)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const getAttentionInfo = (content, status, modified) => {
  const lines = String(content || '').split('\n')
  const statusLine = String(status || '')

  for (const matcher of ATTENTION_MATCHERS) {
    const lineIndex = lines.findIndex(line => matcher.pattern.test(line))
    if (lineIndex !== -1) {
      const matchedLine = lines[lineIndex]
      const lineTime = parseLineTimestamp(matchedLine)
      const fallbackTime = modified ? new Date(modified) : null
      const sourceTime = lineTime || (fallbackTime && !Number.isNaN(fallbackTime.getTime()) ? fallbackTime : null)
      const stale = sourceTime ? Date.now() - sourceTime.getTime() > STALE_ATTENTION_MS : false
      return {
        reason: matcher.label,
        line: sanitizeLine(matchedLine),
        lineNumber: lineIndex + 1,
        stale,
        staleLabel: stale ? 'Historical' : 'Recent',
      }
    }
  }

  const statusMatcher = ATTENTION_MATCHERS.find(matcher => matcher.pattern.test(statusLine))
  if (statusMatcher) {
    return {
      reason: statusMatcher.label,
      line: sanitizeLine(statusLine),
      lineNumber: null,
      stale: false,
      staleLabel: 'Recent',
    }
  }

  return null
}

const getTitle = (item, parsed, source) => {
  if (parsed?.task) return parsed.task
  if (parsed?.title) return parsed.title
  if (parsed?.name) return parsed.name
  if (parsed?.target && parsed?.preset) return `${parsed.target} / ${parsed.preset}`
  if (source === 'packet') return item.name.replace(/\.[^.]+$/, '').replace(/^packet_/, 'Packet ')
  return item.name
}

const getStatus = (parsed, content) => {
  const raw = parsed?.status || parsed?.state || parsed?.result?.status
  if (raw) return String(raw)
  if (ATTENTION_PATTERN.test(content || '')) return 'needs attention'
  return 'recorded'
}

const getRoute = (parsed, source) => {
  if (parsed?.route) return parsed.route
  if (parsed?.agent) return parsed.agent
  if (parsed?.target) return parsed.target
  if (source === 'packet') return 'packet'
  return source
}

const normalizeItems = ({ packets = [], logs = [], results = [] }) => {
  const mapItem = (item, source) => {
    const parsed = parseContent(item.content)
    const status = getStatus(parsed, item.content)
    const title = getTitle(item, parsed, source)
    const route = getRoute(parsed, source)
    const created = parsed?.created || parsed?.createdAt || parsed?.timestamp || parsed?.updatedAt
    const modified = item.modified || created
    const attentionInfo = getAttentionInfo(item.content, status, modified)
    const attention = source === 'log'
      ? Boolean(attentionInfo) || ATTENTION_PATTERN.test(item.content || '') || ATTENTION_PATTERN.test(status)
      : ATTENTION_PATTERN.test(status) || Boolean(attentionInfo) || ATTENTION_PATTERN.test(item.content || '')

    return {
      id: `${source}:${item.name}`,
      source,
      name: item.name,
      title,
      route,
      status,
      modified,
      created,
      attention,
      attentionInfo,
      parsed,
      content: item.content || '',
      size: item.content?.length || 0,
    }
  }

  return [
    ...results.map(item => mapItem(item, 'result')),
    ...logs.map(item => mapItem(item, 'log')),
    ...packets.map(item => mapItem(item, 'packet')),
  ].sort((a, b) => new Date(b.modified || 0) - new Date(a.modified || 0))
}

const redactPreview = content => {
  if (!content) return '(empty file)'
  const text = content.length > MAX_PREVIEW_CHARS
    ? `${content.slice(0, MAX_PREVIEW_CHARS)}\n\n[Preview truncated]`
    : content

  return text
    .split('\n')
    .map(line => (SECRET_LINE_PATTERN.test(line) ? '[redacted sensitive line]' : line))
    .join('\n')
}

const EmptyState = ({ section, hasQuery }) => {
  const Icon = SECTION_CONFIG[section]?.icon || FileText
  const label = SECTION_CONFIG[section]?.label || 'History'
  return (
    <div className="rounded-lg border border-softgraph bg-graphite px-6 py-12 text-center">
      <Icon size={28} className="mx-auto mb-3 text-taupe" />
      <div className="text-sm font-medium text-stone">
        {hasQuery ? 'No matching records' : `${label} is empty`}
      </div>
      <div className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-taupe">
        {hasQuery
          ? 'Adjust the search or section filter to widen the history view.'
          : 'Local packets, results, and logs will appear here after files are written to the existing workspace folders.'}
      </div>
    </div>
  )
}

const StatCard = ({ label, value, icon: Icon, active, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className={`rounded-lg border p-4 text-left transition-colors ${
      active ? 'border-champagne bg-softgraph' : 'border-softgraph bg-graphite hover:border-taupe'
    }`}
  >
    <div className="mb-3 flex items-center justify-between gap-3">
      <span className="text-xs font-semibold uppercase tracking-wider text-taupe">{label}</span>
      <Icon size={14} className={active ? 'text-champagne' : 'text-taupe'} />
    </div>
    <div className="font-mono text-2xl font-semibold text-ivory">{value}</div>
  </button>
)

const HistoryRow = ({ item, selected, onSelect }) => {
  const meta = SOURCE_META[item.source]
  const Icon = meta.icon
  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      className={`w-full rounded-lg border p-4 text-left transition-colors ${
        selected ? 'border-champagne bg-softgraph' : 'border-softgraph bg-graphite hover:border-taupe'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <span className={`mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded border border-softgraph bg-ink ${meta.tone}`}>
            <Icon size={15} />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-semibold text-ivory">{item.title}</span>
              {item.attention ? (
                <span className="inline-flex items-center gap-1 rounded border border-clay/50 bg-clay/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-stone">
                  <AlertTriangle size={10} className="text-clay" />
                  {item.attentionInfo?.reason || 'Attention'}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded border border-olive/40 bg-olive/10 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-stone">
                  <CheckCircle2 size={10} className="text-olive" />
                  {item.status}
                </span>
              )}
            </div>
            <div className="mt-1 truncate text-xs text-taupe">{item.name}</div>
            {item.attentionInfo?.line && (
              <div className="mt-2 truncate font-mono text-[11px] text-stone">
                {item.attentionInfo.lineNumber ? `Line ${item.attentionInfo.lineNumber}: ` : ''}
                {item.attentionInfo.line}
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-mono uppercase tracking-wider text-taupe">
              <span>{meta.label}</span>
              <span>Route: {item.route}</span>
              <span>{formatTime(item.modified)}</span>
              {item.attentionInfo && <span>{item.attentionInfo.staleLabel}</span>}
            </div>
          </div>
        </div>
        <div className="flex-shrink-0 text-right text-[11px] font-mono text-taupe">
          {item.size.toLocaleString()} chars
        </div>
      </div>
    </button>
  )
}

const DetailPanel = ({ item }) => {
  if (!item) {
    return (
      <aside className="rounded-lg border border-softgraph bg-graphite p-5">
        <div className="mb-3 flex items-center gap-2">
          <FileText size={14} className="text-taupe" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Preview</h2>
        </div>
        <div className="flex min-h-[24rem] items-center justify-center rounded border border-softgraph bg-ink px-6 text-center text-sm text-taupe">
          Select a history item to inspect its local read-only preview.
        </div>
      </aside>
    )
  }

  const meta = SOURCE_META[item.source]
  const Icon = meta.icon
  const preview = redactPreview(item.content)

  return (
    <aside className="rounded-lg border border-softgraph bg-graphite p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2">
            <Icon size={14} className={meta.tone} />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-taupe">Preview</h2>
          </div>
          <h3 className="truncate text-base font-semibold text-ivory">{item.title}</h3>
          <div className="mt-1 truncate text-xs text-taupe">{item.name}</div>
        </div>
        {item.attention && <AlertTriangle size={16} className="flex-shrink-0 text-clay" />}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 text-xs">
        <div className="rounded border border-softgraph bg-ink p-3">
          <div className="font-mono uppercase tracking-wider text-taupe">Type</div>
          <div className="mt-1 text-stone">{meta.label}</div>
        </div>
        <div className="rounded border border-softgraph bg-ink p-3">
          <div className="font-mono uppercase tracking-wider text-taupe">Status</div>
          <div className="mt-1 text-stone">{item.attention ? item.attentionInfo?.reason || 'Needs attention' : item.status}</div>
        </div>
        <div className="rounded border border-softgraph bg-ink p-3">
          <div className="font-mono uppercase tracking-wider text-taupe">Route</div>
          <div className="mt-1 text-stone">{item.route}</div>
        </div>
        <div className="rounded border border-softgraph bg-ink p-3">
          <div className="font-mono uppercase tracking-wider text-taupe">Updated</div>
          <div className="mt-1 text-stone">{formatTime(item.modified)}</div>
        </div>
        {item.attentionInfo && (
          <div className="col-span-2 rounded border border-clay/40 bg-clay/10 p-3">
            <div className="font-mono uppercase tracking-wider text-taupe">
              Matched {item.attentionInfo.lineNumber ? `line ${item.attentionInfo.lineNumber}` : 'status'} - {item.attentionInfo.staleLabel}
            </div>
            <div className="mt-1 font-mono text-[11px] leading-relaxed text-stone">{item.attentionInfo.line}</div>
          </div>
        )}
      </div>

      <pre className="max-h-[32rem] overflow-auto rounded border border-softgraph bg-ink p-4 text-xs leading-relaxed text-stone whitespace-pre-wrap">
        {preview}
      </pre>
      <div className="mt-3 text-[11px] leading-relaxed text-taupe">
        Preview redacts lines that look like secrets, tokens, OAuth values, credentials, or chat IDs. The backend endpoints remain local and read-only.
      </div>
    </aside>
  )
}

export default function LogsResults() {
  const [section, setSection] = useState('all')
  const [query, setQuery] = useState('')
  const [data, setData] = useState({ packets: null, logs: null, results: null })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [packetsRes, logsRes, resultsRes] = await Promise.all([getPackets(), getLogs(), getResults()])
      setData({
        packets: packetsRes.packets || [],
        logs: logsRes.logs || [],
        results: resultsRes.results || [],
      })
    } catch {
      setError('Could not load local history. The backend may be offline.')
      setData({ packets: [], logs: [], results: [] })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const allItems = useMemo(() => normalizeItems({
    packets: data.packets || [],
    logs: data.logs || [],
    results: data.results || [],
  }), [data])

  const stats = useMemo(() => ({
    all: allItems.length,
    results: allItems.filter(item => item.source === 'result').length,
    logs: allItems.filter(item => item.source === 'log').length,
    runs: allItems.filter(item => item.source === 'packet').length,
    attention: allItems.filter(item => item.attention).length,
  }), [allItems])

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase()
    return allItems.filter(item => {
      const sectionMatch =
        section === 'all' ||
        (section === 'results' && item.source === 'result') ||
        (section === 'logs' && item.source === 'log') ||
        (section === 'runs' && item.source === 'packet') ||
        (section === 'attention' && item.attention)
      if (!sectionMatch) return false
      if (!q) return true
      return [item.title, item.name, item.route, item.status, item.content]
        .some(value => String(value || '').toLowerCase().includes(q))
    })
  }, [allItems, query, section])

  const selectedItem = filteredItems.find(item => item.id === selectedId) || filteredItems[0] || null

  useEffect(() => {
    if (!selectedItem) {
      setSelectedId(null)
      return
    }
    if (selectedItem.id !== selectedId) setSelectedId(selectedItem.id)
  }, [selectedItem, selectedId])

  const sections = [
    ['all', SECTION_CONFIG.all],
    ['results', SECTION_CONFIG.results],
    ['logs', SECTION_CONFIG.logs],
    ['runs', SECTION_CONFIG.runs],
    ['attention', SECTION_CONFIG.attention],
  ]

  return (
    <div className="max-w-7xl space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-champagne">Cockpit History</p>
          <h1 className="mt-1 text-2xl font-semibold text-ivory">Logs & Results</h1>
          <p className="mt-1 max-w-2xl text-sm text-taupe">
            Review recent agent outputs, local result files, logs, and packet status from the existing read-only dashboard routes.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-2 rounded bg-softgraph px-3 py-2 text-xs font-mono text-taupe transition-colors hover:text-stone"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          Refresh history
        </button>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {sections.map(([id, config]) => (
          <StatCard
            key={id}
            label={config.label}
            value={stats[id]}
            icon={config.icon}
            active={section === id}
            onClick={() => setSection(id)}
          />
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <div className="space-y-4">
          <div className="rounded-lg border border-softgraph bg-graphite p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-2">
                <ListFilter size={14} className="text-taupe" />
                <span className="text-xs font-semibold uppercase tracking-wider text-taupe">
                  {SECTION_CONFIG[section].label}
                </span>
                <span className="font-mono text-xs text-stone">{filteredItems.length} shown</span>
              </div>
              <label className="flex min-w-0 items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 lg:w-72">
                <Search size={13} className="flex-shrink-0 text-taupe" />
                <input
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  placeholder="Filter history"
                  className="min-w-0 flex-1 bg-transparent text-sm text-ivory placeholder-taupe/60 outline-none"
                />
              </label>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-clay/50 bg-clay/10 px-4 py-3 text-sm text-stone">
              {error}
            </div>
          )}

          {loading && (
            <div className="rounded-lg border border-softgraph bg-graphite px-6 py-12 text-center text-xs font-mono text-taupe">
              Loading local history...
            </div>
          )}

          {!loading && filteredItems.length === 0 && (
            <EmptyState section={section} hasQuery={Boolean(query.trim())} />
          )}

          {!loading && filteredItems.length > 0 && (
            <div className="space-y-3">
              {filteredItems.map(item => (
                <HistoryRow
                  key={item.id}
                  item={item}
                  selected={selectedItem?.id === item.id}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          )}
        </div>

        <DetailPanel item={selectedItem} />
      </section>
    </div>
  )
}
