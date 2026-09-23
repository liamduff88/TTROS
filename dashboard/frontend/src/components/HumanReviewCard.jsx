import { useEffect, useRef, useState } from 'react'
import { closeQueueItemReview, getQueueItem, recordQueueOutreachEvent, saveQueueReviewNote } from '../api'
import { applyReviewDecision, loadReviewDraft, persistReviewDraft, saveReviewNoteDraft } from '../reviewCardState'

const storage = () => globalThis.localStorage

const displayTokenLines = lines => Array.isArray(lines) ? lines.filter(Boolean) : []
const isoToday = () => new Date().toISOString().slice(0, 10)

const preparedOutreachCopy = review => {
  const copy = review?.copy || {}
  const stage = review?.stage
  const dueReady = !review?.due_date || review.due_date <= isoToday()
  if (stage === 'draft_ready') return { label: 'Email 1', ...copy.email_1 }
  if (stage === 'email_follow_up_waiting' && dueReady) return { label: 'Email 2', ...copy.email_2 }
  if (stage === 'invitation_ready') return { label: 'LinkedIn connection note', ...copy.linkedin_invitation }
  if (stage === 'linkedin_first_message_ready') return { label: 'First LinkedIn message', ...copy.linkedin_first_message }
  if (stage === 'linkedin_follow_up_waiting' && dueReady) return { label: 'LinkedIn follow-up', ...copy.linkedin_follow_up }
  if (stage === 'linkedin_soft_close_waiting' && dueReady) return { label: 'LinkedIn soft close', ...copy.linkedin_soft_close }
  return null
}

export function HumanReviewCard({ item, onSaved, onOpenArtifact, className = '' }) {
  const [reviewItem, setReviewItem] = useState(item)
  const [draft, setDraft] = useState(() => loadReviewDraft(item.id, storage()))
  const [outreachEvent, setOutreachEvent] = useState('')
  const [occurredOn, setOccurredOn] = useState(isoToday())
  const [eventNote, setEventNote] = useState('')
  const [feedback, setFeedback] = useState({ kind: '', text: '' })
  const savingRef = useRef(false)
  const details = reviewItem.review_details || {}
  const receipt = reviewItem.latest_receipt || {}
  const artifact = reviewItem.primary_artifact || reviewItem.integrated_review_artifact || null
  const tokenLines = displayTokenLines(details.token_usage_lines || receipt.token_usage_lines)

  useEffect(() => {
    let alive = true
    setReviewItem(item)
    setDraft(loadReviewDraft(item.id, storage()))
    setFeedback({ kind: '', text: '' })
    setOutreachEvent('')
    setOccurredOn(isoToday())
    setEventNote('')
    savingRef.current = false
    if (!item.detail_loaded) {
      getQueueItem(item.id)
        .then(result => { if (alive && result?.item) setReviewItem(result.item) })
        .catch(error => {
          if (alive) setFeedback({ kind: 'error', text: error?.response?.data?.detail || error?.message || 'Review detail could not be loaded.' })
        })
    }
    return () => { alive = false }
  }, [item.id])

  const updateNote = note => {
    const next = { note }
    setDraft(next)
    persistReviewDraft(item.id, next, storage())
    if (feedback.text) setFeedback({ kind: '', text: '' })
  }

  const saveNote = async () => {
    if (savingRef.current) return
    savingRef.current = true
    setFeedback({ kind: 'saving', text: 'Saving review note…' })
    try {
      const result = await saveReviewNoteDraft({ itemId: item.id, draft, saveNote: saveQueueReviewNote, storage: storage() })
      if (result?.item) setReviewItem(result.item)
      setDraft({ note: '' })
      setFeedback({ kind: 'success', text: 'Review note saved. Status is still human review.' })
      await onSaved?.(result, 'note')
    } catch (error) {
      setFeedback({ kind: 'error', text: error?.response?.data?.detail || error?.message || 'Review note save failed.' })
    } finally {
      savingRef.current = false
    }
  }

  const decide = async decision => {
    const labels = { approve: 'Approve', needs_changes: 'Needs changes', block: 'Block' }
    const effects = {
      approve: 'move this item from human review to done',
      needs_changes: 'send this item through the existing correction path',
      block: 'mark this item blocked',
    }
    if (!globalThis.confirm?.(`${labels[decision]} ${item.id}? This will ${effects[decision]}.`)) return
    if (savingRef.current) return
    savingRef.current = true
    setFeedback({ kind: 'saving', text: `Applying ${labels[decision]}…` })
    try {
      const result = await applyReviewDecision({
        itemId: item.id,
        decision,
        note: draft.note,
        closeReview: closeQueueItemReview,
      })
      setFeedback({ kind: 'success', text: `${labels[decision]} applied.` })
      await onSaved?.(result, decision)
    } catch (error) {
      setFeedback({ kind: 'error', text: error?.response?.data?.detail || error?.message || 'Review action failed.' })
    } finally {
      savingRef.current = false
    }
  }

  const saving = feedback.kind === 'saving'
  const outreach = reviewItem.outreach_review
  const prepared = preparedOutreachCopy(outreach)
  const allowedEvents = Array.isArray(outreach?.allowed_events) ? outreach.allowed_events : []
  const selectedEvent = outreachEvent || allowedEvents[0] || ''

  const recordEvent = async () => {
    if (!selectedEvent || savingRef.current) return
    if (!globalThis.confirm?.(`Record ${selectedEvent} for ${outreach?.prospect?.person_name}? This changes only the local outreach state.`)) return
    savingRef.current = true
    setFeedback({ kind: 'saving', text: `Recording ${selectedEvent}…` })
    try {
      const result = await recordQueueOutreachEvent(item.id, { event: selectedEvent, occurred_on: occurredOn, note: eventNote })
      if (result?.item) setReviewItem(result.item)
      setOutreachEvent('')
      setEventNote('')
      setFeedback({ kind: 'success', text: `${selectedEvent} recorded. No platform action was performed.` })
      await onSaved?.(result, 'outreach_event')
    } catch (error) {
      setFeedback({ kind: 'error', text: error?.response?.data?.detail || error?.message || 'Outreach event could not be recorded.' })
    } finally {
      savingRef.current = false
    }
  }

  if (reviewItem.review_card_kind === 'outreach' && !outreach) {
    return <article className={`rounded-lg border border-champagne/60 bg-graphite p-3 text-sm text-taupe ${className}`} data-review-card-id={item.id}>Loading outreach review…</article>
  }

  if (outreach) return (
    <article className={`overflow-hidden rounded-lg border border-champagne/60 bg-graphite ${className}`} data-review-card-id={item.id} data-review-card-kind="outreach">
      <header className="border-b border-softgraph px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <div><h2 className="text-sm font-semibold leading-5 text-ivory">{reviewItem.title}</h2><div className="mt-1 font-mono text-[10px] text-taupe">{reviewItem.id}</div></div>
          <span className="shrink-0 rounded border border-champagne/40 bg-champagne/10 px-2 py-1 text-[10px] font-semibold uppercase text-champagne">Human review</span>
        </div>
      </header>
      <div className="space-y-3 p-3" data-review-card-body>
        <section className="rounded border border-softgraph bg-ink p-3 text-xs">
          <div className="text-sm font-semibold text-ivory">{outreach.prospect?.person_name} · {outreach.prospect?.company_name}</div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-taupe">
            <div><span className="block text-[10px] uppercase">Channel</span><span className="text-stone">{outreach.channel}</span></div>
            <div><span className="block text-[10px] uppercase">Stage</span><span className="text-stone">{String(outreach.stage || '').replaceAll('_', ' ')}</span></div>
            <div><span className="block text-[10px] uppercase">Due date</span><span className="text-stone">{outreach.due_date || 'conditional event only'}</span></div>
            <div><span className="block text-[10px] uppercase">Score / readiness</span><span className="text-stone">{outreach.score} · {outreach.readiness}</span></div>
          </div>
          <div className="mt-2 text-taupe"><span className="font-semibold text-stone">Source:</span> {outreach.source_handoff}</div>
        </section>

        <section className="rounded border border-softgraph bg-ink p-3 text-xs">
          <div className="font-semibold text-stone">Primary signal</div><p className="mt-1 whitespace-pre-wrap leading-5 text-taupe">{outreach.primary_signal}</p>
          <div className="mt-2 font-semibold text-stone">Main caution</div><p className="mt-1 whitespace-pre-wrap leading-5 text-taupe">{outreach.main_caution}</p>
        </section>

        {outreach.reconciliation?.focused_review_question && <section className="rounded border border-champagne/40 bg-champagne/10 p-3 text-xs text-champagne"><span className="font-semibold">Focused check:</span> {outreach.reconciliation.focused_review_question}</section>}

        {outreach.profile_url && <a className="block rounded border border-softgraph bg-ink p-3 text-xs font-semibold text-champagne hover:text-stone" href={outreach.profile_url} target="_blank" rel="noreferrer">Open exact public LinkedIn profile</a>}
        {outreach.gmail_draft_url && <a className="block rounded border border-softgraph bg-ink p-3 text-xs font-semibold text-champagne hover:text-stone" href={outreach.gmail_draft_url} target="_blank" rel="noreferrer">Open Gmail draft · {outreach.gmail_draft_reference}</a>}

        {prepared ? <section className="rounded border border-softgraph bg-ink p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">{prepared.label}</div>
          {prepared.subject && <div className="mt-2 text-sm font-semibold text-stone">Subject: {prepared.subject}</div>}
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-stone">{prepared.body}</pre>
        </section> : <section className="rounded border border-softgraph bg-ink p-3 text-xs text-taupe">Later-stage copy is retained but inactive until its recorded prerequisite event and due date.</section>}

        <section className="rounded border border-champagne/40 bg-champagne/10 p-3 text-xs">
          <div className="font-semibold uppercase tracking-wider text-champagne">Exact Liam action</div>
          <p className="mt-1 leading-5 text-stone">{outreach.exact_action}</p>
          {(outreach.manual_review_metadata || []).map(value => <p key={value} className="mt-1 text-taupe">{value}</p>)}
        </section>

        <section className="rounded border border-softgraph bg-ink p-3">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-taupe" htmlFor={`outreach-event-${item.id}`}>Record actual outcome</label>
          <select id={`outreach-event-${item.id}`} value={selectedEvent} onChange={event => setOutreachEvent(event.target.value)} className="mt-2 h-9 w-full rounded border border-softgraph bg-graphite px-2 text-xs text-stone">
            {allowedEvents.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
          </select>
          <input type="date" value={occurredOn} onChange={event => setOccurredOn(event.target.value)} className="mt-2 h-9 w-full rounded border border-softgraph bg-graphite px-2 text-xs text-stone" aria-label={`Outreach event date for ${item.id}`} />
          <textarea value={eventNote} onChange={event => setEventNote(event.target.value)} maxLength={500} placeholder="Optional event note" className="mt-2 min-h-16 w-full resize-y rounded border border-softgraph bg-graphite px-3 py-2 text-xs text-stone" />
          <button type="button" onClick={recordEvent} disabled={saving || !selectedEvent} className="mt-2 w-full rounded bg-champagne px-3 py-2 text-sm font-semibold text-ivory hover:bg-well disabled:opacity-60">Record actual outcome</button>
          <p className="mt-1 text-[11px] text-taupe">This records what Liam already did or observed. It never sends email or performs a LinkedIn action.</p>
        </section>
        {feedback.text && <p className={`text-xs font-mono ${feedback.kind === 'error' ? 'text-clay' : 'text-champagne'}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p>}
      </div>
    </article>
  )

  return (
    <article className={`overflow-hidden rounded-lg border border-champagne/60 bg-graphite ${className}`} data-review-card-id={item.id}>
      <header className="border-b border-softgraph px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="break-words text-sm font-semibold leading-5 text-ivory">{reviewItem.title || 'Untitled task'}</h2>
            <div className="mt-1 font-mono text-[10px] text-taupe">{reviewItem.id}</div>
          </div>
          <span className="shrink-0 rounded border border-champagne/40 bg-champagne/10 px-2 py-1 text-[10px] font-semibold uppercase text-champagne">Human review</span>
        </div>
      </header>

      <div className="space-y-3 p-3" data-review-card-body>
        <section className="rounded border border-softgraph bg-ink p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Summary</div>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-5 text-stone">{details.summary || reviewItem.summary_for_operator || 'Substantive summary unavailable.'}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-taupe sm:grid-cols-4">
            <div><span className="block text-[10px] uppercase">Worker</span><span className="text-stone">{details.worker || reviewItem.owner || 'unavailable'}</span></div>
            <div><span className="block text-[10px] uppercase">Attempts</span><span className="text-stone">{details.attempts ?? 'unavailable'}</span></div>
            <div className="col-span-2"><span className="block text-[10px] uppercase">Validation</span><span className="text-stone">{details.validation || 'unavailable'}</span></div>
          </div>
          {details.failure_explanation && <div className="mt-2 rounded border border-clay/30 bg-clay/10 p-2 text-xs text-clay"><span className="font-semibold">Failure explanation:</span> {details.failure_explanation}</div>}
          {tokenLines.length > 0 && <div className="mt-2 text-xs text-taupe"><span className="font-semibold text-stone">Token usage:</span> {tokenLines.join(' · ')}</div>}
        </section>

        <section className="rounded border border-softgraph bg-ink p-3" data-testid="review-receipt-content">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Latest substantive receipt</div>
            {receipt.path && (
              <button type="button" className="text-xs text-champagne hover:text-stone" onClick={() => onOpenArtifact?.({ path: receipt.path, category: 'Receipt', extension: '.md' })}>
                Full receipt
              </button>
            )}
          </div>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-stone">{details.receipt_content || receipt.content || 'Receipt unavailable.'}</pre>
        </section>

        {artifact && <section className="rounded border border-softgraph bg-ink p-3" data-testid="review-artifact-content">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Consolidated artifact</div>
            {artifact.path && (
              <button type="button" className="text-xs text-champagne hover:text-stone" onClick={() => onOpenArtifact?.({ path: artifact.path, category: 'Artifact', extension: artifact.extension, name: artifact.name })}>
                Full artifact
              </button>
            )}
          </div>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-stone">{artifact.content || artifact.content_excerpt || 'Artifact preview unavailable.'}</pre>
        </section>}

        <section className="rounded border border-softgraph bg-ink p-3">
          <label className="text-[11px] font-semibold uppercase tracking-wider text-taupe" htmlFor={`review-note-${item.id}`}>Optional review note</label>
          <textarea
            id={`review-note-${item.id}`}
            aria-label={`Review note for ${item.id}`}
            className="mt-2 min-h-20 w-full resize-y rounded border border-softgraph bg-graphite px-3 py-2 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne"
            maxLength={500}
            value={draft.note}
            onChange={event => updateNote(event.target.value)}
            placeholder="Optional note for approval, correction, or block context"
          />
          <button type="button" onClick={saveNote} disabled={saving} className="mt-2 rounded border border-softgraph px-3 py-2 text-xs font-semibold text-stone hover:border-champagne disabled:opacity-60">Save review note</button>
          <p className="mt-1 text-[11px] text-taupe">Saving this note never changes item status.</p>
        </section>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button type="button" onClick={() => decide('approve')} disabled={saving} className="rounded bg-champagne px-3 py-2 text-sm font-semibold text-ivory hover:bg-well disabled:opacity-60">Approve</button>
          <button type="button" onClick={() => decide('needs_changes')} disabled={saving} className="rounded border border-champagne/50 px-3 py-2 text-sm font-semibold text-champagne hover:bg-champagne/10 disabled:opacity-60">Needs changes</button>
          <button type="button" onClick={() => decide('block')} disabled={saving} className="rounded border border-clay/50 px-3 py-2 text-sm font-semibold text-clay hover:bg-clay/10 disabled:opacity-60">Block</button>
        </div>

        {feedback.text && <p className={`text-xs font-mono ${feedback.kind === 'error' ? 'text-clay' : 'text-champagne'}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p>}
      </div>
    </article>
  )
}
