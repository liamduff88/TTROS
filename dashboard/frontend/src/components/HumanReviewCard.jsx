import { useEffect, useRef, useState } from 'react'
import { closeQueueItemReview } from '../api'
import { loadReviewDraft, persistReviewDraft, REVIEW_CLOSE_STATUSES, saveReviewDraft } from '../reviewCardState'

const statusLabel = (status, item) => ({
  done: 'Done',
  needs_input: item?.owner_type === 'workflow' ? 'Needs changes' : 'Needs input',
  blocked: 'Blocked',
}[status] || status)

const storage = () => globalThis.localStorage

export function HumanReviewCard({ item, onSaved, className = '' }) {
  const [draft, setDraft] = useState(() => loadReviewDraft(item.id, storage()))
  const [feedback, setFeedback] = useState({ kind: '', text: '' })
  const [saved, setSaved] = useState(false)
  const savingRef = useRef(false)

  useEffect(() => {
    setDraft(loadReviewDraft(item.id, storage()))
    setFeedback({ kind: '', text: '' })
    setSaved(false)
    savingRef.current = false
  }, [item.id])

  useEffect(() => {
    if (item.status !== 'human_review') return
    setSaved(false)
    savingRef.current = false
  }, [item.status])

  useEffect(() => {
    if (!feedback.text || feedback.kind === 'saving') return undefined
    const timeout = globalThis.setTimeout(() => setFeedback({ kind: '', text: '' }), 5000)
    return () => globalThis.clearTimeout(timeout)
  }, [feedback])

  const updateDraft = next => {
    setDraft(next)
    persistReviewDraft(item.id, next, storage())
    if (feedback.text) setFeedback({ kind: '', text: '' })
  }

  const save = async event => {
    event.preventDefault()
    if (savingRef.current) return
    savingRef.current = true
    setSaved(false)
    setFeedback({ kind: 'saving', text: 'Saving…' })
    try {
      const result = await saveReviewDraft({
        itemId: item.id,
        draft,
        closeReview: closeQueueItemReview,
        storage: storage(),
      })
      setSaved(true)
      setFeedback({ kind: 'success', text: 'Saved.' })
      Promise.resolve(onSaved?.(result, draft.status)).catch(() => {})
    } catch (error) {
      setSaved(false)
      setFeedback({
        kind: 'error',
        text: error?.response?.data?.detail || error?.message || 'Save failed.',
      })
    } finally {
      savingRef.current = false
    }
  }

  const saving = feedback.kind === 'saving'
  return (
    <article
      className={`overflow-hidden rounded-lg border border-champagne/60 bg-graphite ${className}`}
      data-review-card-id={item.id}
    >
      <header className="border-b border-softgraph px-3 py-3">
        <h2 className="break-words text-sm font-semibold leading-5 text-ivory">
          <span className="font-mono text-champagne">{item.id}</span> — {item.title}
        </h2>
      </header>
      <form className="space-y-3 p-3" onSubmit={save} data-review-card-body>
        <textarea
          aria-label={`Receipt for ${item.id}`}
          className="min-h-24 w-full resize-y rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne"
          maxLength={500}
          value={draft.receipt}
          onChange={event => updateDraft({ ...draft, receipt: event.target.value })}
          placeholder="Receipt"
        />
        <select
          aria-label={`Review-close status for ${item.id}`}
          className="h-10 w-full rounded border border-softgraph bg-ink px-3 text-sm text-stone outline-none focus:border-champagne"
          value={draft.status}
          onChange={event => updateDraft({ ...draft, status: event.target.value })}
        >
          {REVIEW_CLOSE_STATUSES.map(status => <option key={status} value={status}>{statusLabel(status, item)}</option>)}
        </select>
        <button
          type="submit"
          disabled={saving || saved || item.status !== 'human_review'}
          className="inline-flex h-10 w-full items-center justify-center rounded bg-champagne px-3 text-sm font-semibold text-ivory transition-colors hover:bg-well focus:outline-none focus:ring-2 focus:ring-champagne/70 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Save/Attach
        </button>
        {feedback.text && (
          <p
            className={`text-xs font-mono ${feedback.kind === 'error' ? 'text-clay' : 'text-champagne'}`}
            role={feedback.kind === 'error' ? 'alert' : 'status'}
          >
            {feedback.text}
          </p>
        )}
      </form>
    </article>
  )
}
