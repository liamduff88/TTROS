import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Download, ExternalLink, FileText, Folder, FolderOpen, LockKeyhole, Monitor, Play, RefreshCw, Upload } from 'lucide-react'
import { ActionButton, EmptyState, HubTabs, PageHeader } from '../components/DashboardKit'
import {
  downloadRemotePcFile, getRemotePcReceipt, getRemotePcReceipts, getRemotePcStatus, listRemotePcFiles,
  prepareRemotePcUpload, prepareRemotePowerShell, revealRemotePcPath, runRemotePowerShell, uploadRemotePcFile,
} from '../api'

// Remote PC — real control of the Windows host from the Dashboard. The backend
// (dashboard/backend/remote_pc.py) verifies the operator identity on every
// route and binds each PowerShell run or upload to a single-use confirmation
// of the exact action; this view only collects input and shows the results.

const TABS = [
  { id: 'powershell', label: 'PowerShell' },
  { id: 'files', label: 'Files' },
  { id: 'desktop', label: 'Desktop' },
  { id: 'receipts', label: 'Receipts' },
]

const errorText = error => error?.response?.data?.detail || error?.message || 'Request failed'
const formatBytes = value => {
  if (value === null || value === undefined) return ''
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`
}
const formatWhen = value => {
  const time = Date.parse(value || '')
  return Number.isNaN(time) ? '' : new Date(time).toLocaleString()
}
const joinWindowsPath = (folder, name) => `${folder.replace(/\\+$/, '')}\\${name}`

function Card({ title, children, className = '' }) {
  return (
    <div className={`min-w-0 rounded border border-softgraph bg-graphite/70 p-3 ${className}`}>
      {title && <div className="mb-1 text-[11px] uppercase tracking-wide text-taupe">{title}</div>}
      {children}
    </div>
  )
}

function Dot({ ok }) {
  return <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${ok ? 'bg-olive' : 'bg-clay'}`} />
}

function StatusStrip({ status }) {
  const windows = status?.windows || {}
  const tailscale = status?.tailscale || {}
  const desktop = status?.desktop || {}
  const operator = status?.operator || {}
  const pathLabel = operator.access_path === 'cloudflare_access' ? 'Cloudflare Access' : 'Tailscale'
  return (
    <div className="mb-4 grid grid-cols-2 gap-2 lg:grid-cols-4" data-testid="remote-pc-status">
      <Card title="Windows">
        <div className="text-sm font-semibold text-ivory"><Dot ok={windows.reachable} />{windows.reachable ? (windows.computer || 'Reachable') : 'Unreachable'}</div>
        <div className="mt-0.5 truncate text-xs text-taupe">{windows.reachable ? `${windows.user || ''} · build ${windows.build || '?'}` : (windows.error || '')}</div>
      </Card>
      <Card title="Signed in">
        <div className="truncate text-sm font-semibold text-ivory">{operator.identity || '—'}</div>
        <div className="mt-0.5 text-xs text-taupe">via {pathLabel}</div>
      </Card>
      <Card title="Tailscale">
        <div className="text-sm font-semibold text-ivory"><Dot ok={tailscale.online} />{tailscale.online ? 'Online' : 'Offline'}</div>
        <div className="mt-0.5 truncate text-xs text-taupe">{tailscale.funnel_enabled ? 'Funnel ON (public) — check' : 'tailnet only'}</div>
      </Card>
      <Card title="Desktop">
        <div className="text-sm font-semibold text-ivory"><Dot ok={desktop.state === 'ready'} />{desktop.state === 'ready' ? 'Ready' : desktop.state === 'installed_not_running' ? 'Host stopped' : 'Not set up'}</div>
        <div className="mt-0.5 truncate text-xs text-taupe">{desktop.solution || ''}</div>
      </Card>
    </div>
  )
}

function ConfirmDialog({ title, children, confirmLabel, busy, onCancel, onConfirm }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/80 p-3 sm:items-center" role="dialog" aria-modal="true" data-testid="remote-pc-confirm">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded border border-clay/60 bg-graphite p-4">
        <div className="flex items-center gap-2 text-clay"><LockKeyhole size={16} /><h3 className="font-semibold">{title}</h3></div>
        <div className="mt-3 text-sm text-stone">{children}</div>
        <div className="mt-4 flex justify-end gap-2">
          <ActionButton className="h-10" onClick={onCancel} disabled={busy}>Cancel</ActionButton>
          <ActionButton kind="locked" className="h-10" onClick={onConfirm} disabled={busy} data-testid="remote-pc-confirm-run">{busy ? 'Working…' : confirmLabel}</ActionButton>
        </div>
      </div>
    </div>
  )
}

function OutputBlock({ label, text, tone = 'text-stone', wrap, testid }) {
  if (!text) return null
  return (
    <div className="mt-3 min-w-0">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-taupe">{label}</div>
      <pre data-testid={testid} className={`max-h-[50vh] overflow-auto rounded border border-softgraph bg-ink p-3 font-mono text-xs leading-5 ${tone} ${wrap ? 'whitespace-pre-wrap break-words' : 'whitespace-pre'}`}>{text}</pre>
    </div>
  )
}

function RunResult({ result }) {
  const [wrap, setWrap] = useState(true)
  if (!result) return null
  const ok = result.exit_code === 0 && !result.timed_out
  return (
    <div className="mt-4 rounded border border-softgraph bg-graphite/60 p-3" data-testid="remote-pc-result">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded border px-2 py-0.5 font-semibold ${ok ? 'border-olive/60 bg-olive/15 text-stone' : 'border-clay/70 bg-clay/15 text-clay'}`} data-testid="remote-pc-exit-code">exit {result.exit_code}</span>
        {result.timed_out && <span className="rounded border border-clay/70 bg-clay/15 px-2 py-0.5 font-semibold text-clay">timed out after {result.timeout_seconds}s</span>}
        <span className="text-taupe">{(result.duration_ms / 1000).toFixed(1)}s</span>
        <span className="min-w-0 truncate font-mono text-taupe" title={result.receipt_path}>receipt {result.receipt_id}</span>
        <button className="ml-auto text-taupe underline-offset-2 hover:text-stone hover:underline" onClick={() => setWrap(value => !value)}>{wrap ? 'No wrap' : 'Wrap'}</button>
      </div>
      {!result.stdout && !result.stderr && <div className="mt-3 text-xs text-taupe">No output.</div>}
      <OutputBlock label={`stdout${result.stdout_truncated ? ' (truncated)' : ''}`} text={result.stdout} wrap={wrap} testid="remote-pc-stdout" />
      <OutputBlock label={`stderr${result.stderr_truncated ? ' (truncated)' : ''}`} text={result.stderr} tone="text-clay" wrap={wrap} testid="remote-pc-stderr" />
    </div>
  )
}

function PowerShellPanel({ status, receipts, onRan }) {
  const [command, setCommand] = useState('')
  const [timeoutSeconds, setTimeoutSeconds] = useState(60)
  const [pending, setPending] = useState(null)
  const [running, setRunning] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const timeouts = status?.executor?.timeouts || [30, 60, 120, 300]
  const windows = status?.windows || {}

  useEffect(() => {
    if (!running) return undefined
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 500)
    return () => window.clearInterval(timer)
  }, [running])

  const prepare = async () => {
    setError('')
    try {
      const prepared = await prepareRemotePowerShell(command, timeoutSeconds)
      setPending({ ...prepared, command, timeoutSeconds })
    } catch (err) {
      setError(errorText(err))
    }
  }

  const run = async () => {
    const job = pending
    setRunning(true)
    setElapsed(0)
    setError('')
    try {
      const outcome = await runRemotePowerShell(job.command, job.timeoutSeconds, job.confirmation_token)
      setResult(outcome)
      onRan?.()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setRunning(false)
      setPending(null)
    }
  }

  const history = (receipts || []).filter(row => row.action === 'powershell').slice(0, 8)
  return (
    <div className="min-w-0">
      <label className="mb-1 block text-xs text-taupe" htmlFor="remote-pc-command">
        PowerShell on {windows.computer || 'Windows'} as {windows.user || 'the signed-in Windows user'} — sent exactly as typed
      </label>
      <textarea
        id="remote-pc-command"
        data-testid="remote-pc-command"
        value={command}
        onChange={event => setCommand(event.target.value)}
        onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && command.trim()) prepare() }}
        rows={5}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        autoComplete="off"
        placeholder="Get-Process | Sort-Object CPU -Descending | Select-Object -First 10"
        className="w-full resize-y rounded border border-softgraph bg-ink p-3 font-mono text-[13px] leading-5 text-ivory placeholder:text-taupe/60 focus:border-champagne/60 focus:outline-none"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-xs text-taupe">
          Timeout
          <select value={timeoutSeconds} onChange={event => setTimeoutSeconds(Number(event.target.value))} className="h-10 rounded border border-softgraph bg-ink px-2 text-xs text-stone">
            {timeouts.map(value => <option key={value} value={value}>{value}s</option>)}
          </select>
        </label>
        <ActionButton kind="primary" className="ml-auto h-10 px-4" onClick={prepare} disabled={!command.trim() || running} data-testid="remote-pc-run">
          {running ? <><RefreshCw size={14} className="animate-spin" /> Running {elapsed}s</> : <><Play size={14} /> Run</>}
        </ActionButton>
      </div>
      <div className="mt-1 text-[11px] text-taupe">Every run asks you to confirm the exact command and writes a receipt. Ctrl/⌘+Enter to run.</div>
      {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay" data-testid="remote-pc-error">{error}</div>}
      <RunResult result={result} />

      {history.length > 0 && (
        <div className="mt-5">
          <div className="mb-1 text-[11px] uppercase tracking-wide text-taupe">Recent commands</div>
          {history.map(row => (
            <button key={row.receipt_id} onClick={() => setCommand(row.summary)} className="mb-1 flex w-full min-w-0 items-center gap-2 rounded border border-softgraph bg-graphite/50 px-2 py-2 text-left text-xs hover:border-champagne/40" title="Load into the editor">
              <span className={`shrink-0 rounded px-1.5 font-mono ${row.exit_code === 0 ? 'text-olive' : 'text-clay'}`}>{row.timed_out ? 'T/O' : row.exit_code}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-stone">{row.summary}</span>
            </button>
          ))}
        </div>
      )}

      {pending && (
        <ConfirmDialog title="Run this on Windows?" confirmLabel="Run on Windows" busy={running} onCancel={() => setPending(null)} onConfirm={run}>
          <div className="text-xs text-taupe">Runs on <b className="text-stone">{windows.computer || 'Windows'}</b> as <b className="text-stone">{windows.user || 'the signed-in user'}</b>, timeout {pending.timeoutSeconds}s. This cannot be undone from here.</div>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded border border-softgraph bg-ink p-3 font-mono text-xs text-ivory" data-testid="remote-pc-confirm-command">{pending.command}</pre>
          <div className="mt-1 font-mono text-[10px] text-taupe">sha256 {pending.command_sha256.slice(0, 16)}… · {pending.characters} chars · confirmation valid {pending.expires_in_seconds}s</div>
        </ConfirmDialog>
      )}
    </div>
  )
}

function FilesPanel({ onChanged }) {
  const [path, setPath] = useState('C:\\Users\\Admin')
  const [input, setInput] = useState('C:\\Users\\Admin')
  const [listing, setListing] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [upload, setUpload] = useState(null)
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)

  const load = async target => {
    setLoading(true)
    setError('')
    try {
      const data = await listRemotePcFiles(target)
      setListing(data)
      setPath(data.path)
      setInput(data.path)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(path) }, [])

  const download = async entry => {
    setError('')
    setNotice(`Downloading ${entry.name}…`)
    try {
      const blob = await downloadRemotePcFile(joinWindowsPath(path, entry.name))
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = entry.name
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 30000)
      setNotice(`Downloaded ${entry.name}`)
      onChanged?.()
    } catch (err) {
      setNotice('')
      setError(errorText(err))
    }
  }

  const chooseUpload = async event => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setError('')
    try {
      const prepared = await prepareRemotePcUpload(path, file.name, file.size)
      setUpload({ file, ...prepared })
    } catch (err) {
      setError(errorText(err))
    }
  }

  const confirmUpload = async () => {
    setBusy(true)
    try {
      const receipt = await uploadRemotePcFile(path, upload.file, upload.confirmation_token)
      setNotice(`Uploaded ${receipt.windows_path} (${formatBytes(receipt.bytes)})`)
      setUpload(null)
      onChanged?.()
      load(path)
    } catch (err) {
      setError(errorText(err))
      setUpload(null)
    } finally {
      setBusy(false)
    }
  }

  const reveal = async () => {
    setError('')
    try {
      await revealRemotePcPath(path)
      setNotice(`Opened ${path} in Explorer on the PC`)
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div className="min-w-0">
      <form className="flex min-w-0 gap-2" onSubmit={event => { event.preventDefault(); load(input) }}>
        <input
          value={input}
          onChange={event => setInput(event.target.value)}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          className="h-10 min-w-0 flex-1 rounded border border-softgraph bg-ink px-3 font-mono text-xs text-ivory focus:border-champagne/60 focus:outline-none"
          aria-label="Windows folder path"
          data-testid="remote-pc-path"
        />
        <ActionButton type="submit" className="h-10">Go</ActionButton>
      </form>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <ActionButton className="h-10" disabled={!listing?.parent} onClick={() => load(listing.parent)}><ArrowUp size={14} /> Up</ActionButton>
        {(listing?.drives || []).map(drive => (
          <ActionButton key={drive} className="h-10" onClick={() => load(drive)}>{drive}</ActionButton>
        ))}
        <ActionButton className="h-10" onClick={() => load(path)}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /></ActionButton>
        <div className="ml-auto flex gap-2">
          <ActionButton className="h-10" onClick={reveal} title="Open this folder in Explorer on the PC desktop"><FolderOpen size={14} /> Show on PC</ActionButton>
          <ActionButton kind="token" className="h-10" onClick={() => fileInput.current?.click()}><Upload size={14} /> Upload</ActionButton>
          <input ref={fileInput} type="file" className="hidden" onChange={chooseUpload} data-testid="remote-pc-upload-input" />
        </div>
      </div>
      {error && <div className="mt-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay">{error}</div>}
      {notice && !error && <div className="mt-3 text-xs text-taupe">{notice}</div>}
      <div className="mt-3 overflow-hidden rounded border border-softgraph" data-testid="remote-pc-listing">
        {(listing?.entries || []).map(entry => (
          <div key={entry.name} className="flex min-h-11 min-w-0 items-center gap-2 border-b border-softgraph/60 bg-graphite/40 px-2 last:border-b-0">
            {entry.type === 'folder' ? (
              <button className="flex min-h-11 min-w-0 flex-1 items-center gap-2 text-left text-sm text-stone hover:text-ivory" onClick={() => load(joinWindowsPath(path, entry.name))}>
                <Folder size={15} className="shrink-0 text-champagne" />
                <span className="truncate">{entry.name}</span>
              </button>
            ) : (
              <>
                <FileText size={15} className="shrink-0 text-taupe" />
                <span className="min-w-0 flex-1 truncate text-sm text-stone" title={entry.name}>{entry.name}</span>
                <span className="hidden shrink-0 text-xs text-taupe sm:inline">{formatWhen(entry.modified)}</span>
                <span className="w-16 shrink-0 text-right text-xs text-taupe">{formatBytes(entry.size)}</span>
                {entry.type === 'file' && (
                  <button className="flex h-10 w-10 shrink-0 items-center justify-center rounded text-taupe hover:bg-softgraph hover:text-ivory" onClick={() => download(entry)} aria-label={`Download ${entry.name}`} title="Download">
                    <Download size={15} />
                  </button>
                )}
              </>
            )}
          </div>
        ))}
        {listing && listing.entries.length === 0 && <div className="p-3 text-xs text-taupe">Empty folder.</div>}
        {listing?.truncated && <div className="p-2 text-xs text-taupe">Showing the first {listing.entries.length} entries.</div>}
      </div>
      <div className="mt-2 text-[11px] text-taupe">Browse and download freely. Uploads ask for confirmation, never overwrite, and write a receipt. To rename, move or delete, use PowerShell.</div>

      {upload && (
        <ConfirmDialog title="Upload to Windows?" confirmLabel="Upload" busy={busy} onCancel={() => setUpload(null)} onConfirm={confirmUpload}>
          <div className="text-xs text-taupe">Creates a new file. An existing file is never overwritten.</div>
          <div className="mt-2 break-all rounded border border-softgraph bg-ink p-3 font-mono text-xs text-ivory">{upload.windows_path}</div>
          <div className="mt-1 text-xs text-taupe">{formatBytes(upload.file.size)}</div>
        </ConfirmDialog>
      )}
    </div>
  )
}

function DesktopPanel({ status }) {
  const desktop = status?.desktop || {}
  const ready = desktop.state === 'ready'
  return (
    <div className="min-w-0 space-y-3" data-testid="remote-pc-desktop">
      <Card>
        <div className="flex items-center gap-2 text-sm font-semibold text-ivory"><Monitor size={16} className="text-champagne" /> {desktop.solution || 'Chrome Remote Desktop'}</div>
        <div className="mt-1 text-sm text-stone">
          {ready && 'The host service is running on this PC. Open it from your phone or any browser and enter your PIN.'}
          {desktop.state === 'installed_not_running' && 'The host is installed but its service is not running. Start it with PowerShell: Start-Service chromoting (needs admin), or re-enable remote access at the link below.'}
          {desktop.state === 'not_installed' && 'Not set up yet. Interactive desktop access is not available until the host is installed on this PC.'}
        </div>
        {ready ? (
          <a href={desktop.launch_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex h-10 items-center gap-2 rounded border border-champagne/80 bg-champagne px-4 text-xs font-semibold text-ivory hover:bg-well">
            <ExternalLink size={14} /> Open Chrome Remote Desktop
          </a>
        ) : (
          <a href={desktop.setup_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex h-10 items-center gap-2 rounded border border-softgraph bg-softgraph/40 px-4 text-xs font-semibold text-stone hover:bg-softgraph">
            <ExternalLink size={14} /> remotedesktop.google.com/access
          </a>
        )}
      </Card>
      {!ready && (
        <Card title="One-time setup">
          <ol className="list-decimal space-y-1.5 pl-5 text-sm text-stone">
            <li>At the PC, open <span className="font-mono text-xs">remotedesktop.google.com/access</span> in Chrome and sign in with your Google account.</li>
            <li>Choose <b>Set up remote access</b>, install the host, and approve the Windows administrator (UAC) prompt.</li>
            <li>Name the computer and choose a PIN of at least 6 digits.</li>
            <li>On your iPhone, install <b>Chrome Remote Desktop</b> from the App Store and sign in with the same account.</li>
          </ol>
          <div className="mt-2 text-xs text-taupe">{desktop.requires_at_pc}</div>
        </Card>
      )}
      <Card title="Why this option">
        <div className="text-xs text-taupe">{desktop.why}</div>
        <div className="mt-1 text-xs text-taupe">The Dashboard does not embed a desktop viewer: it opens the Chrome Remote Desktop client, which carries its own sign-in and PIN. PowerShell and Files on this page keep working whether or not the desktop host is installed.</div>
      </Card>
    </div>
  )
}

function ReceiptsPanel({ receipts, receiptsDir, onRefresh }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const open = async id => {
    setError('')
    try {
      setDetail(await getRemotePcReceipt(id))
    } catch (err) {
      setError(errorText(err))
    }
  }
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center gap-2">
        <div className="min-w-0 flex-1 truncate font-mono text-[11px] text-taupe" title={receiptsDir}>{receiptsDir}</div>
        <ActionButton className="h-10" onClick={onRefresh}><RefreshCw size={14} /> Refresh</ActionButton>
      </div>
      {error && <div className="mb-2 text-xs text-clay">{error}</div>}
      {(receipts || []).length === 0 && <EmptyState title="No receipts yet" detail="Each PowerShell run, upload and download writes one." />}
      {(receipts || []).map(row => (
        <button key={row.receipt_id} onClick={() => open(row.receipt_id)} className="mb-1 flex w-full min-w-0 flex-col rounded border border-softgraph bg-graphite/50 px-3 py-2 text-left hover:border-champagne/40" data-testid="remote-pc-receipt-row">
          <div className="flex w-full items-center gap-2 text-xs">
            <span className="font-semibold text-stone">{row.action.replace('_', ' ')}</span>
            {row.action === 'powershell' && <span className={row.exit_code === 0 && !row.timed_out ? 'text-olive' : 'text-clay'}>{row.timed_out ? 'timed out' : `exit ${row.exit_code}`}</span>}
            <span className="ml-auto shrink-0 text-taupe">{formatWhen(row.started_at)}</span>
          </div>
          <div className="mt-0.5 w-full truncate font-mono text-xs text-taupe">{row.summary}</div>
        </button>
      ))}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/80 p-3 sm:items-center" onClick={() => setDetail(null)}>
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded border border-softgraph bg-graphite p-4" onClick={event => event.stopPropagation()}>
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1 truncate font-mono text-xs text-champagne">{detail.receipt_id}</div>
              <ActionButton onClick={() => setDetail(null)}>Close</ActionButton>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-taupe">
              <div>By {detail.operator?.identity}</div><div>via {detail.operator?.access_path}</div>
              <div>{formatWhen(detail.started_at)}</div><div>{detail.duration_ms !== undefined ? `${(detail.duration_ms / 1000).toFixed(1)}s · exit ${detail.exit_code}` : formatBytes(detail.bytes)}</div>
            </div>
            {detail.command && <OutputBlock label="Command" text={detail.command} tone="text-ivory" wrap />}
            {detail.windows_path && <OutputBlock label="Path" text={detail.windows_path} tone="text-ivory" wrap />}
            <OutputBlock label="stdout" text={detail.stdout} wrap />
            <OutputBlock label="stderr" text={detail.stderr} tone="text-clay" wrap />
          </div>
        </div>
      )}
    </div>
  )
}

export default function RemotePC({ initialFilters, onViewParamsChange }) {
  const requested = initialFilters?.tab
  const [tab, setTab] = useState(TABS.some(item => item.id === requested) ? requested : 'powershell')
  const [status, setStatus] = useState(null)
  const [statusError, setStatusError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [receipts, setReceipts] = useState([])
  const [receiptsDir, setReceiptsDir] = useState('')

  const loadStatus = async (refresh = false) => {
    setLoading(true)
    try {
      setStatus(await getRemotePcStatus(refresh))
      setStatusError(null)
    } catch (err) {
      setStatusError({ code: err?.response?.status, detail: errorText(err) })
    } finally {
      setLoading(false)
    }
  }
  const loadReceipts = () => getRemotePcReceipts()
    .then(data => { setReceipts(data.receipts || []); setReceiptsDir(data.receipts_dir || '') })
    .catch(() => {})

  useEffect(() => {
    loadStatus()
    loadReceipts()
  }, [])

  const changeTab = id => {
    setTab(id)
    onViewParamsChange?.({ ...(initialFilters || {}), tab: id })
  }

  const header = (
    <PageHeader
      title="Remote PC"
      question={status?.windows?.computer ? `${status.windows.computer} · ${status.windows.os || 'Windows'}` : 'Control the Windows host from anywhere'}
      actions={<ActionButton className="h-10" onClick={() => loadStatus(true)}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Status</ActionButton>}
    />
  )

  if (statusError?.code === 403) {
    return (
      <div className="min-w-0" data-testid="remote-pc">
        {header}
        <EmptyState
          title="Remote PC is locked on this connection"
          detail={`${statusError.detail}. Remote PC needs a verified identity: open the Dashboard through ttros.timetorevenue.com (Cloudflare Access) or vrs-global.tailb38520.ts.net (Tailscale).`}
        />
      </div>
    )
  }

  return (
    <div className="min-w-0" data-testid="remote-pc">
      {header}
      {statusError && <div className="mb-3 rounded border border-clay/60 bg-clay/10 p-2 text-xs text-clay">Status unavailable: {statusError.detail}</div>}
      {status ? <StatusStrip status={status} /> : <div className="mb-4 text-xs text-taupe">{loading ? 'Checking Windows…' : ''}</div>}
      <HubTabs tabs={TABS} active={tab} onChange={changeTab} />
      {tab === 'powershell' && <PowerShellPanel status={status} receipts={receipts} onRan={loadReceipts} />}
      {tab === 'files' && <FilesPanel onChanged={loadReceipts} />}
      {tab === 'desktop' && <DesktopPanel status={status} />}
      {tab === 'receipts' && <ReceiptsPanel receipts={receipts} receiptsDir={receiptsDir} onRefresh={loadReceipts} />}
    </div>
  )
}
