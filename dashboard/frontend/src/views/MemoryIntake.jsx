import { useEffect, useRef, useState } from 'react'
import { AlertCircle, FileText, RefreshCw, Upload } from 'lucide-react'
import {
  getMemoryIntake,
  getMemoryIntakeUnfiledPreview,
  getUpload,
  ingestMemoryIntakeInboxPath,
  ingestMemoryIntakeUpload,
  uploadFile,
} from '../api'
import { ActionButton, DetailPanel, EmptyState, PageHeader, StatusChip } from '../components/DashboardKit'

const formatBytes = value => {
  const bytes = Number(value)
  if (!Number.isFinite(bytes)) return 'unavailable'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const errorText = error => {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : error?.message || 'Request failed.'
}

const recentStatusTone = status => ({ ingested: 'Done', duplicate: 'Done', needs_attention: 'Blocked', failed: 'Blocked' }[status] || 'Unavailable')

const recentStatusLabel = status => ({
  ingested: 'Ingested',
  duplicate: 'Already ingested',
  needs_attention: 'Needs attention',
  failed: 'Failed',
}[status] || status || 'Unavailable')

function RecentRow({ row }) {
  return (
    <div
      className="w-full rounded border border-softgraph bg-graphite/50 p-3 text-left"
      data-testid="memory-intake-recent-row"
      data-status={row.status}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-semibold text-stone">{row.filename || 'Unnamed source'}</span>
        <StatusChip status={recentStatusTone(row.status)}>{recentStatusLabel(row.status)}</StatusChip>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1 text-[11px] text-taupe md:grid-cols-4">
        <span>Source card: {row.source_card_present ? 'verified' : row.source_card_created ? 'created; verification pending' : 'not available'}</span>
        <span>Original preserved: {row.original_preserved ? 'yes' : 'unavailable'}</span>
        <span>Search updated: {row.search_updated || 'unavailable'}</span>
        <span>Graph updated: {row.graph_updated || 'unavailable'}</span>
      </div>
      {row.error && <div className="mt-2 text-xs text-clay">Retry: fix the error below, then Ingest again. {row.error}</div>}
    </div>
  )
}

export function MemoryIntakeQuickDropCard({ onNavigate }) {
  const [snapshot, setSnapshot] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)

  const load = () => getMemoryIntake().then(setSnapshot).catch(() => {})
  useEffect(() => { load() }, [])

  const addFiles = async fileList => {
    const files = Array.from(fileList || [])
    if (!files.length) return
    setError('')
    for (const file of files) {
      try {
        await uploadFile(file)
      } catch (err) {
        setError(errorText(err))
      }
    }
    load()
  }

  const readyCount = snapshot?.counts?.ready ?? 0
  const ingestedRecent = snapshot?.counts?.ingested_recent ?? 0

  return (
    <div
      className={`rounded border p-4 ${dragOver ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-graphite/70'}`}
      onDragOver={event => { event.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={event => { event.preventDefault(); setDragOver(false); addFiles(event.dataTransfer.files) }}
      data-testid="cockpit-memory-intake-card"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-stone">Add to Memory</h2>
        <button onClick={() => onNavigate?.('memory-intake')} className="text-xs font-semibold text-champagne hover:text-stone" data-testid="cockpit-open-memory-intake">Open Add to Memory</button>
      </div>
      <p className="mt-1 text-xs text-taupe">Drop a file, or browse, to queue it for the Business Brain.</p>
      <input ref={fileInputRef} type="file" multiple className="hidden" data-testid="cockpit-memory-intake-file-input" onChange={event => { addFiles(event.target.files); event.target.value = '' }} />
      <button onClick={() => fileInputRef.current?.click()} className="mt-3 w-full rounded border border-dashed border-softgraph bg-ink py-3 text-xs text-taupe hover:border-champagne/50" data-testid="cockpit-memory-intake-browse">
        Browse files
      </button>
      {error && <div className="mt-2 text-xs text-clay">{error}</div>}
      <div className="mt-3 grid grid-cols-2 gap-2 text-center text-xs">
        <div className="rounded bg-ink p-2"><div className="text-lg font-semibold text-ivory" data-testid="cockpit-memory-intake-ready-count">{readyCount}</div><div className="text-taupe">Ready</div></div>
        <div className="rounded bg-ink p-2"><div className="text-lg font-semibold text-ivory" data-testid="cockpit-memory-intake-ingested-count">{ingestedRecent}</div><div className="text-taupe">Ingested recently</div></div>
      </div>
    </div>
  )
}

export default function MemoryIntake({ onNavigate }) {
  const [snapshot, setSnapshot] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(new Set())
  const [busyKeys, setBusyKeys] = useState(new Set())
  const [dragOver, setDragOver] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [preview, setPreview] = useState(null)
  const fileInputRef = useRef(null)

  const load = () => {
    setLoading(true)
    return getMemoryIntake().then(setSnapshot).catch(() => setSnapshot(current => current)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const ready = snapshot?.ready || []
  const unfiled = snapshot?.unfiled || []
  const recent = snapshot?.recent || []
  const integrity = snapshot?.brain_index_integrity

  const withBusy = async (key, action) => {
    setBusyKeys(current => new Set(current).add(key))
    try {
      await action()
    } finally {
      setBusyKeys(current => { const next = new Set(current); next.delete(key); return next })
    }
  }

  const addFiles = async fileList => {
    const files = Array.from(fileList || [])
    if (!files.length) return
    setUploadError('')
    for (const file of files) {
      try {
        await uploadFile(file)
      } catch (error) {
        setUploadError(errorText(error))
      }
    }
    load()
  }

  const onDrop = event => {
    event.preventDefault()
    setDragOver(false)
    addFiles(event.dataTransfer.files)
  }

  const toggleSelected = uploadId => setSelected(current => {
    const next = new Set(current)
    if (next.has(uploadId)) next.delete(uploadId)
    else next.add(uploadId)
    return next
  })

  const selectableIds = ready.filter(row => row.supported).map(row => row.upload_id)
  const allSelected = selectableIds.length > 0 && selectableIds.every(id => selected.has(id))

  const toggleSelectAll = () => setSelected(allSelected ? new Set() : new Set(selectableIds))

  const ingestUpload = uploadId => withBusy(`upload-${uploadId}`, () => ingestMemoryIntakeUpload(uploadId).then(load))

  const ingestSelected = () => withBusy('bulk', async () => {
    for (const uploadId of selected) {
      await ingestMemoryIntakeUpload(uploadId).catch(() => {})
    }
    setSelected(new Set())
    await load()
  })

  const ingestInbox = path => withBusy(`inbox-${path}`, () => ingestMemoryIntakeInboxPath(path).then(load))

  const previewUpload = row => withBusy(`preview-upload-${row.upload_id}`, () =>
    getUpload(row.upload_id).then(detail => setPreview({ title: row.original_filename || row.stored_filename, body: detail.preview || '[No preview available for this file type.]' })))

  const previewUnfiled = row => withBusy(`preview-inbox-${row.path}`, () =>
    getMemoryIntakeUnfiledPreview(row.path).then(detail => setPreview({ title: row.filename, body: detail.preview || '[No preview available.]' })))

  return (
    <>
      <PageHeader
        title="Add to Memory"
        question="Bring a file into the Business Brain, on your say — nothing here is promoted automatically."
        actions={<ActionButton onClick={load}><RefreshCw size={13} />Refresh</ActionButton>}
      />

      {integrity && !integrity.ok && (
        <div className="mb-4 rounded border border-clay/70 bg-clay/10 p-3 text-sm text-clay" data-testid="memory-intake-integrity-warning">
          <div className="flex items-center gap-2"><AlertCircle size={14} />Business Brain source-intake index needs attention.</div>
          <div className="mt-1 text-xs text-clay/90">
            {integrity.missing_card_links?.length ? `${integrity.missing_card_links.length} card link(s) missing from sources/intake/INDEX.md. ` : ''}
            {integrity.missing_record_links?.length ? `${integrity.missing_record_links.length} record link(s) missing. ` : ''}
            {!integrity.index_present ? 'Index file is missing.' : ''}
          </div>
        </div>
      )}

      <section
        onDragOver={event => { event.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`rounded border-2 border-dashed p-8 text-center transition-colors ${dragOver ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-graphite/50'}`}
        data-testid="memory-intake-dropzone"
      >
        <Upload size={22} className="mx-auto text-taupe" />
        <div className="mt-2 text-sm text-stone">Drop files here</div>
        <div className="mt-1 text-xs text-taupe">.md, .txt, .eml supported end-to-end today. Other types upload but stay unsupported for ingestion.</div>
        <input ref={fileInputRef} type="file" multiple className="hidden" data-testid="memory-intake-file-input" onChange={event => { addFiles(event.target.files); event.target.value = '' }} />
        <ActionButton kind="primary" className="mt-3" onClick={() => fileInputRef.current?.click()}>Browse files</ActionButton>
        {uploadError && <div className="mt-2 text-xs text-clay">{uploadError}</div>}
      </section>

      <section className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-stone">Ready to ingest</h2>
          <div className="flex items-center gap-2">
            <button onClick={toggleSelectAll} className="text-xs font-semibold text-champagne hover:text-stone" data-testid="memory-intake-select-all">
              {allSelected ? 'Clear selection' : 'Select all'}
            </button>
            <ActionButton kind="primary" disabled={!selected.size || busyKeys.has('bulk')} onClick={ingestSelected} data-testid="memory-intake-ingest-selected">
              Ingest selected ({selected.size})
            </ActionButton>
          </div>
        </div>
        <div className="space-y-2" data-testid="memory-intake-ready-list">
          {ready.map(row => (
            <div key={row.upload_id} className="flex items-center gap-3 rounded border border-softgraph bg-graphite/50 p-3" data-upload-id={row.upload_id}>
              {row.supported ? (
                <input type="checkbox" checked={selected.has(row.upload_id)} onChange={() => toggleSelected(row.upload_id)} aria-label={`Select ${row.original_filename}`} />
              ) : <span className="w-4" />}
              <FileText size={14} className="shrink-0 text-taupe" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-stone">{row.original_filename}</div>
                <div className="text-xs text-taupe">{row.stored_filename?.split('.').pop() || 'unknown'} · {formatBytes(row.size)}{!row.supported && ` · ${row.support_note || 'unsupported'}`}</div>
              </div>
              <ActionButton onClick={() => previewUpload(row)} disabled={busyKeys.has(`preview-upload-${row.upload_id}`)}>Preview</ActionButton>
              <ActionButton kind="primary" disabled={!row.supported || busyKeys.has(`upload-${row.upload_id}`)} onClick={() => ingestUpload(row.upload_id)}>Ingest</ActionButton>
            </div>
          ))}
          {!loading && !ready.length && <EmptyState title="Nothing waiting." detail="Drop or browse a file above to see it here." />}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-stone">New &amp; unfiled</h2>
        <p className="mb-2 text-xs text-taupe">Already discovered by the existing watched Inbox and search-indexed — not yet Business Brain sources until you choose to ingest them.</p>
        <div className="space-y-2" data-testid="memory-intake-unfiled-list">
          {unfiled.map(row => (
            <div key={row.path} className="flex items-center gap-3 rounded border border-softgraph bg-graphite/50 p-3">
              <FileText size={14} className="shrink-0 text-taupe" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-stone">{row.filename}</div>
                <div className="text-xs text-taupe">{formatBytes(row.size)}{row.already_in_brain ? ' · already in Business Brain' : ''}{!row.supported ? ' · unsupported type' : ''}</div>
              </div>
              <ActionButton onClick={() => previewUnfiled(row)} disabled={busyKeys.has(`preview-inbox-${row.path}`)}>Preview</ActionButton>
              <ActionButton
                kind="primary"
                disabled={!row.supported || row.already_in_brain || busyKeys.has(`inbox-${row.path}`)}
                onClick={() => ingestInbox(row.path)}
              >
                {row.already_in_brain ? 'Already ingested' : 'Ingest to Business Brain'}
              </ActionButton>
            </div>
          ))}
          {!loading && !unfiled.length && <EmptyState title="Nothing new in the watched Inbox." />}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-stone">Ingested / recent results</h2>
        <div className="space-y-2" data-testid="memory-intake-recent-list">
          {recent.map(row => <RecentRow key={row.key} row={row} />)}
          {!recent.length && <EmptyState title="No recent ingestion results." />}
        </div>
      </section>

      <DetailPanel item={preview} title={preview?.title} subtitle="Preview" onClose={() => setPreview(null)}>
        <pre className="max-h-[65vh] overflow-auto whitespace-pre-wrap rounded border border-softgraph bg-ink p-3 text-xs leading-5 text-stone">{preview?.body}</pre>
      </DetailPanel>
    </>
  )
}
