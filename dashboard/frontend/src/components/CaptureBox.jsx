import { useRef, useState } from 'react'
import { Inbox, Paperclip, X } from 'lucide-react'
import { createInboxCapture, ingestMemoryIntakeUpload, uploadFile } from '../api'

// Revisit: when quick note capture or the shared Memory Intake upload contract changes. · Last touched: 2026-09-13.

const newCaptureId = () => globalThis.crypto?.randomUUID?.() || `dashboard-${Date.now()}-${Math.random().toString(16).slice(2)}`
const newPendingId = () => globalThis.crypto?.randomUUID?.() || `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`

const errorText = error => {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : error?.message || 'Request failed'
}

const fileStatusLabel = row => ({
  pending: 'Ready',
  uploading: 'Uploading…',
  ingesting: 'Ingesting…',
  ingested: 'Ingested',
  duplicate: 'Already ingested',
  needs_attention: 'Needs attention',
  failed: 'Failed',
}[row.status] || row.status)

export default function CaptureBox() {
  const [text, setText] = useState('')
  const [files, setFiles] = useState([])
  const [focused, setFocused] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [state, setState] = useState({ status: 'idle', message: '' })
  const captureId = useRef(newCaptureId())
  const fileInputRef = useRef(null)

  const addFiles = fileList => {
    const added = Array.from(fileList || []).map(file => ({ id: newPendingId(), file, status: 'pending', message: '' }))
    if (!added.length) return
    setFiles(current => [...current, ...added])
    setState({ status: 'idle', message: '' })
  }

  const updateFile = (id, next) => setFiles(current => current.map(row => row.id === id ? { ...row, ...next } : row))
  const removeFile = id => setFiles(current => current.filter(row => row.id !== id))
  const busy = state.status === 'saving'
  const hasPendingFiles = files.some(row => ['pending', 'failed', 'needs_attention'].includes(row.status))
  const canSubmit = Boolean(text.trim()) || hasPendingFiles

  const submit = async event => {
    event?.preventDefault()
    if (!canSubmit || busy) return

    const cleanText = text.trim()
    const fileBatch = files.filter(row => ['pending', 'failed', 'needs_attention'].includes(row.status))
    setState({ status: 'saving', message: cleanText && fileBatch.length ? 'Capturing note and adding files…' : cleanText ? 'Capturing…' : 'Adding files…' })

    let noteOutcome = null
    if (cleanText) {
      try {
        const result = await createInboxCapture(text, captureId.current)
        noteOutcome = { success: true, duplicate: Boolean(result.duplicate) }
        setText('')
        captureId.current = newCaptureId()
      } catch (error) {
        noteOutcome = { success: false, error: errorText(error) }
      }
    }

    const fileOutcomes = []
    for (const row of fileBatch) {
      updateFile(row.id, { status: 'uploading', message: 'Uploading with shared /api/uploads…' })
      try {
        const uploaded = await uploadFile(row.file)
        updateFile(row.id, { status: 'ingesting', message: 'Running full Memory Intake…', uploadId: uploaded.upload_id })
        const ingested = await ingestMemoryIntakeUpload(uploaded.upload_id)
        const status = ingested.status || (ingested.success ? 'ingested' : 'needs_attention')
        const message = ingested.error || (status === 'duplicate'
          ? 'Original and Card already exist.'
          : ingested.success ? 'Original, Card, INDEX, Search, and Graphify verified.' : 'Ingestion did not complete.')
        updateFile(row.id, { status, message, uploadId: uploaded.upload_id })
        fileOutcomes.push({ success: Boolean(ingested.success), status, filename: row.file.name })
      } catch (error) {
        const message = errorText(error)
        updateFile(row.id, { status: 'failed', message })
        fileOutcomes.push({ success: false, status: 'failed', filename: row.file.name })
      }
    }

    const successes = fileOutcomes.filter(row => row.success).length
    const failures = fileOutcomes.length - successes
    const parts = []
    if (noteOutcome?.success) parts.push(noteOutcome.duplicate ? 'Note already captured.' : 'Note captured.')
    if (noteOutcome && !noteOutcome.success) parts.push(`Note failed: ${noteOutcome.error}.`)
    if (fileOutcomes.length) parts.push(`${successes} file${successes === 1 ? '' : 's'} added${failures ? `; ${failures} need${failures === 1 ? 's' : ''} attention` : ''}.`)
    const failed = (noteOutcome && !noteOutcome.success) || failures > 0
    const succeeded = noteOutcome?.success || successes > 0
    setState({ status: failed ? (succeeded ? 'partial' : 'error') : 'saved', message: parts.join(' ') })
  }

  const onKeyDown = event => {
    if (event.key === 'Enter' && event.ctrlKey) submit(event)
  }

  return (
    <form
      onSubmit={submit}
      onDragOver={event => { event.preventDefault(); setDragOver(true) }}
      onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget)) setDragOver(false) }}
      onDrop={event => { event.preventDefault(); setDragOver(false); addFiles(event.dataTransfer.files) }}
      className={`shrink-0 border-b px-3 py-2 transition-colors ${dragOver ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-graphite'}`}
      data-testid="cockpit-capture-box"
    >
      <div className="flex items-end gap-2">
        <Inbox size={15} className="mb-2 text-champagne" aria-hidden="true" />
        <textarea
          value={text}
          rows={focused || text.includes('\n') ? 3 : 1}
          onChange={event => setText(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
          placeholder="Capture a note… Ctrl+Enter"
          aria-label="Capture a note to the Business Brain inbox"
          className="min-h-8 max-h-32 flex-1 resize-none rounded border border-softgraph bg-ink px-3 py-1.5 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne/60"
        />
        <input ref={fileInputRef} type="file" multiple className="hidden" data-testid="quick-add-file-input" onChange={event => { addFiles(event.target.files); event.target.value = '' }} />
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={busy} className="flex h-8 items-center gap-1 rounded border border-softgraph bg-ink px-3 text-xs font-semibold text-stone hover:border-champagne/60 disabled:opacity-50" data-testid="quick-add-browse">
          <Paperclip size={13} />Attach / Browse
        </button>
        <button type="submit" disabled={!canSubmit || busy} className="h-8 rounded border border-champagne/80 bg-champagne px-3 text-xs font-semibold text-ivory disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? 'Adding…' : files.length ? 'Add to Memory' : 'Capture'}
        </button>
      </div>

      {files.length > 0 && (
        <div className="ml-6 mt-2 flex flex-wrap gap-2" data-testid="quick-add-files" aria-label={`${files.length} attached file${files.length === 1 ? '' : 's'}`}>
          {files.map(row => {
            const rowBusy = row.status === 'uploading' || row.status === 'ingesting'
            const failed = row.status === 'failed' || row.status === 'needs_attention'
            return (
              <div key={row.id} className={`max-w-sm rounded border px-2 py-1 text-xs ${failed ? 'border-clay/70 bg-clay/10 text-clay' : 'border-softgraph bg-ink text-taupe'}`} data-testid="quick-add-file-row" data-status={row.status}>
                <div className="flex items-center gap-2">
                  <span className="max-w-52 truncate text-stone" title={row.file.name}>{row.file.name}</span>
                  <span>{fileStatusLabel(row)}</span>
                  {!rowBusy && <button type="button" onClick={() => removeFile(row.id)} aria-label={`Remove ${row.file.name}`} className="rounded text-taupe hover:text-stone"><X size={12} /></button>}
                </div>
                {row.message && <div className="mt-0.5 max-w-80 truncate" title={row.message}>{row.message}</div>}
              </div>
            )
          })}
        </div>
      )}

      {dragOver && <div className="ml-6 mt-1 text-xs font-semibold text-champagne">Drop files to add them to Memory</div>}
      {state.message && <div role="status" data-status={state.status} className={`ml-6 mt-1 text-xs ${state.status === 'error' || state.status === 'partial' ? 'text-clay' : 'text-taupe'}`}>{state.message}</div>}
    </form>
  )
}
