import { useEffect, useRef, useState } from 'react'
import { closeQueueItemReview, getQueueItem, saveQueueReviewNote } from '../api'
import { applyReviewDecision, loadReviewDraft, persistReviewDraft, saveReviewNoteDraft } from '../reviewCardState'

const storage = () => globalThis.localStorage
const fullDocumentHref = (kind, path) => path
  ? `/api/queue/${kind}?path=${encodeURIComponent(path)}`
  : ''

const displayTokenLines = lines => Array.isArray(lines) ? lines.filter(Boolean) : []

export function HumanReviewCard({ item, onSaved, className = '' }) {
  const [reviewItem, setReviewItem] = useState(item)
  const [draft, setDraft] = useState(() => loadReviewDraft(item.id, storage()))
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
  return (
    <article className={`overflow-hidden rounded-lg border border-champagne/60 bg-graphite ${className}`} data-review-card-id={item.id}>
      <header className="border-b border-softgraph px-3 py-3">
        <div className="flex items-start justify-between gap-3">
          <h2 className="break-words text-sm font-semibold leading-5 text-ivory">
            <span className="font-mono text-champagne">{reviewItem.id}</span> — {reviewItem.title}
          </h2>
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
            {receipt.path && <a className="text-xs text-champagne hover:text-stone" href={fullDocumentHref('receipt', receipt.path)} target="_blank" rel="noreferrer">Full receipt</a>}
          </div>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-stone">{details.receipt_content || receipt.content || 'Receipt unavailable.'}</pre>
        </section>

        {artifact && <section className="rounded border border-softgraph bg-ink p-3" data-testid="review-artifact-content">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Consolidated artifact</div>
            {artifact.path && <a className="text-xs text-champagne hover:text-stone" href={fullDocumentHref('artifact', artifact.path)} target="_blank" rel="noreferrer">Full artifact</a>}
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
