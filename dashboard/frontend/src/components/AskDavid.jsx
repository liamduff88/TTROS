// Revisit: when the Ask David primary Cockpit contract changes. · Last touched: 2026-09-13.

import { useEffect, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, ListChecks, Paperclip, Search, Send, Sparkles, X } from 'lucide-react'
import { askDavid, uploadFile } from '../api'
import { loadStoredDraft, loadStoredThread, persistDraft, persistThread } from '../askDavidState'
import { ActionButton, StatusChip } from './DashboardKit'

const entryId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const errorText = error => {
  const detail = error?.response?.data?.detail
  const value = detail?.output || detail || error?.message || 'David could not be reached.'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function AttachmentChip({ attachment, onRemove }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border border-softgraph bg-ink px-2 py-1 text-xs text-stone"
      data-testid="ask-david-attachment-chip"
      data-upload-status={attachment.status}
    >
      <Paperclip size={11} className={attachment.status === 'error' ? 'text-clay' : 'text-taupe'} />
      <span className="max-w-[10rem] truncate">{attachment.filename}</span>
      {attachment.status === 'uploading' && <span className="text-taupe">uploading…</span>}
      {attachment.status === 'error' && <span className="text-clay">failed</span>}
      {onRemove && (
        <button type="button" onClick={onRemove} className="text-taupe hover:text-clay" aria-label={`Remove ${attachment.filename}`}>
          <X size={11} />
        </button>
      )}
    </span>
  )
}

function ReplyCard({ entry, onNavigate }) {
  if (entry.kind === 'deterministic_read') {
    return (
      <div className="rounded border border-olive/50 bg-olive/10 p-3" data-testid="ask-david-deterministic">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-olive"><Search size={13} />Local lookup — no queue, no model call</span>
          <StatusChip status="Done" />
        </div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone">{entry.output}</p>
      </div>
    )
  }
  if (entry.kind === 'memory_intake_ingested') {
    return (
      <div className={`rounded border p-3 ${entry.success ? 'border-olive/50 bg-olive/10' : 'border-clay/70 bg-clay/10'}`} data-testid="ask-david-ingested">
        <div className="flex items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${entry.success ? 'text-olive' : 'text-clay'}`}><Paperclip size={13} />Business Brain ingestion — canonical source intake</span>
          <StatusChip status={entry.success ? 'Done' : 'Blocked'} />
        </div>
        {(entry.results || []).map(row => (
          <p key={row.upload_id} className="mt-2 text-sm text-stone">
            {row.filename}: {row.success ? `${row.status}${row.source_record ? ` · ${row.source_record}` : ''}` : row.error}
          </p>
        ))}
      </div>
    )
  }
  if (entry.kind === 'queue_created') {
    return (
      <div className="rounded border border-champagne/50 bg-champagne/10 p-3" data-testid="ask-david-queued">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-champagne"><ListChecks size={13} />Genuine execution — sent to Operating Hermes</span>
          <StatusChip status="Ready" />
        </div>
        <p className="mt-2 text-sm text-stone">
          Routed <button className="font-mono text-champagne underline-offset-2 hover:underline" onClick={() => onNavigate?.('work-queue', { selectedId: entry.item?.id })}>{entry.item?.id}</button> to {entry.item?.owner || 'the queue'}.
        </p>
        {entry.handed_objective ? (
          <p className="mt-2 text-sm italic leading-6 text-stone" data-testid="ask-david-handed-objective">Handed to Hermes: “{entry.handed_objective}”</p>
        ) : null}
        <div className="mt-1 text-xs text-taupe">{entry.route?.workflow ? `Matched workflow: ${entry.route.workflow}` : 'Matched a recognized command pattern.'}</div>
      </div>
    )
  }
  if (entry.kind === 'david_reply' && entry.success) {
    return (
      <div className="rounded border border-softgraph bg-ink p-3" data-testid="ask-david-reply">
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-champagne"><Sparkles size={13} />David</span>
          <StatusChip status="Done" />
        </div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone">{entry.response}</p>
      </div>
    )
  }
  return (
    <div className="rounded border border-clay/70 bg-clay/10 p-3" role="alert" data-testid="ask-david-failure">
      <div className="flex items-center gap-2 text-clay"><AlertCircle size={14} /><span className="text-xs font-semibold">David could not answer</span></div>
      <p className="mt-2 text-sm text-stone">{entry.error?.message || entry.error || 'No successful response is being shown.'}</p>
    </div>
  )
}

export default function AskDavid({ onNavigate, refresh }) {
  const [text, setText] = useState(() => loadStoredDraft(window.sessionStorage))
  const [thread, setThread] = useState(() => loadStoredThread(window.sessionStorage))
  const [attachments, setAttachments] = useState([])
  const [busy, setBusy] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    persistThread(window.sessionStorage, thread)
  }, [thread])

  useEffect(() => {
    persistDraft(window.sessionStorage, text)
  }, [text])

  const addFiles = async fileList => {
    const files = Array.from(fileList || [])
    for (const file of files) {
      const localId = entryId()
      setAttachments(current => [...current, { localId, filename: file.name, status: 'uploading' }])
      try {
        const result = await uploadFile(file)
        setAttachments(current => current.map(item => item.localId === localId
          ? { ...item, status: 'ready', upload_id: result.upload_id, supported: result.supported }
          : item))
      } catch (error) {
        setAttachments(current => current.map(item => item.localId === localId ? { ...item, status: 'error', error: errorText(error) } : item))
      }
    }
  }

  const onPickFiles = event => {
    addFiles(event.target.files)
    event.target.value = ''
  }

  const removeAttachment = localId => setAttachments(current => current.filter(item => item.localId !== localId))

  const submit = async event => {
    event.preventDefault()
    const clean = text.trim()
    if (busy || (!clean && attachments.length === 0) || attachments.some(item => item.status === 'uploading')) return
    setBusy(true)
    const attachmentRefs = attachments.filter(item => item.upload_id).map(item => `upload:${item.upload_id}`)
    const attachmentSnapshot = attachments.map(item => ({ filename: item.filename, status: item.status, upload_id: item.upload_id }))
    const userEntry = { id: entryId(), type: 'user', text: clean, attachments: attachmentSnapshot }
    setThread(current => [...current, userEntry])
    setText('')
    setAttachments([])
    try {
      const result = await askDavid(clean, attachmentRefs)
      setThread(current => [...current, { id: entryId(), type: 'reply', ...result }])
      if (result?.kind === 'queue_created' || result?.kind === 'memory_intake_ingested') refresh?.()
    } catch (error) {
      // Request never completed: drop the optimistic echo and restore the
      // draft so the failure doesn't look like a send and nothing typed is lost.
      setThread(current => current.filter(entry => entry.id !== userEntry.id))
      setText(clean)
      setAttachments(attachmentSnapshot.map(item => ({ ...item, localId: entryId() })))
      setThread(current => [...current, { id: entryId(), type: 'reply', kind: 'david_reply', success: false, error: errorText(error) }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mb-4 rounded border border-champagne/50 bg-graphite p-4" data-testid="ask-david">
      <div className="flex items-center gap-2 text-xs font-mono text-champagne"><Sparkles size={14} />DAVID · YOUR EXECUTIVE PARTNER</div>
      <h1 className="mt-1 text-xl font-semibold text-ivory">What do you need?</h1>
      <p className="mt-1 text-xs text-taupe">Ask a question, find something, make a decision, or get work done. Attach a file for David to read as source material — he will not save it to the Business Brain unless you explicitly ask him to ingest it.</p>

      {thread.length > 0 && (
        <div className="mt-3 space-y-2" data-testid="ask-david-thread">
          {thread.map(entry => entry.type === 'user' ? (
            <div key={entry.id} className="rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone">
              {entry.text}
              {entry.attachments?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5" data-testid="ask-david-sent-attachments">
                  {entry.attachments.map(item => <AttachmentChip key={item.upload_id || item.filename} attachment={item} />)}
                </div>
              )}
            </div>
          ) : (
            <ReplyCard key={entry.id} entry={entry} onNavigate={onNavigate} />
          ))}
        </div>
      )}

      <form onSubmit={submit} className="mt-3">
        <textarea
          value={text}
          onChange={event => setText(event.target.value)}
          placeholder="Ask a question, find something, make a decision, or get work done…"
          maxLength={8000}
          className="min-h-20 w-full resize-y rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne/60"
        />
        {attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5" data-testid="ask-david-pending-attachments">
            {attachments.map(item => <AttachmentChip key={item.localId} attachment={item} onRemove={() => removeAttachment(item.localId)} />)}
          </div>
        )}
        <div className="mt-2 flex items-center gap-2">
          <input ref={fileInputRef} type="file" multiple className="hidden" data-testid="ask-david-file-input" onChange={onPickFiles} />
          <ActionButton type="button" onClick={() => fileInputRef.current?.click()} aria-label="Attach a file" data-testid="ask-david-attach-button">
            <Paperclip size={13} />Attach
          </ActionButton>
          <ActionButton kind="primary" type="submit" disabled={busy || (!text.trim() && attachments.length === 0)}>
            <Send size={13} />{busy ? 'Asking David…' : 'Ask David'}
          </ActionButton>
          {busy && <span className="text-xs text-champagne" role="status">David is working…</span>}
          {!busy && thread.length > 0 && <CheckCircle2 size={13} className="text-olive" />}
        </div>
      </form>
    </section>
  )
}
