// Revisit: when the Ask David primary Cockpit contract changes. · Last touched: 2026-08-07.

import { useState } from 'react'
import { AlertCircle, CheckCircle2, ListChecks, Search, Send, Sparkles } from 'lucide-react'
import { askDavid } from '../api'
import { ActionButton, StatusChip } from './DashboardKit'

const entryId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const errorText = error => {
  const detail = error?.response?.data?.detail
  const value = detail?.output || detail || error?.message || 'David could not be reached.'
  return typeof value === 'string' ? value : JSON.stringify(value)
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
  const [text, setText] = useState('')
  const [thread, setThread] = useState([])
  const [busy, setBusy] = useState(false)

  const submit = async event => {
    event.preventDefault()
    const clean = text.trim()
    if (!clean || busy) return
    setBusy(true)
    const userEntry = { id: entryId(), type: 'user', text: clean }
    setThread(current => [...current, userEntry])
    setText('')
    try {
      const result = await askDavid(clean)
      setThread(current => [...current, { id: entryId(), type: 'reply', ...result }])
      if (result?.kind === 'queue_created') refresh?.()
    } catch (error) {
      setThread(current => [...current, { id: entryId(), type: 'reply', kind: 'david_reply', success: false, error: errorText(error) }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mb-4 rounded border border-champagne/50 bg-graphite p-4" data-testid="ask-david">
      <div className="flex items-center gap-2 text-xs font-mono text-champagne"><Sparkles size={14} />DAVID · YOUR EXECUTIVE PARTNER</div>
      <h1 className="mt-1 text-xl font-semibold text-ivory">What do you need?</h1>
      <p className="mt-1 text-xs text-taupe">Ask a question, find something, make a decision, or get work done. David reads a local answer when one exists, replies directly for ordinary judgment, and only hands work to Operating Hermes when it is genuine execution.</p>

      {thread.length > 0 && (
        <div className="mt-3 space-y-2" data-testid="ask-david-thread">
          {thread.map(entry => entry.type === 'user' ? (
            <div key={entry.id} className="rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone">{entry.text}</div>
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
        <div className="mt-2 flex items-center gap-2">
          <ActionButton kind="primary" type="submit" disabled={busy || !text.trim()}>
            <Send size={13} />{busy ? 'Asking David…' : 'Ask David'}
          </ActionButton>
          {busy && <span className="text-xs text-champagne" role="status">David is working…</span>}
          {!busy && thread.length > 0 && <CheckCircle2 size={13} className="text-olive" />}
        </div>
      </form>
    </section>
  )
}
