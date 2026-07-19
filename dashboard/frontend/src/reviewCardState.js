const REVIEW_DRAFT_PREFIX = 'aos.dashboard.review-card.v1.'

export const reviewDraftKey = itemId => `${REVIEW_DRAFT_PREFIX}${itemId}`

const usableStorage = storage => storage && typeof storage.getItem === 'function'

export const emptyReviewDraft = () => ({ note: '' })

export function loadReviewDraft(itemId, storage = globalThis.localStorage) {
  if (!itemId || !usableStorage(storage)) return emptyReviewDraft()
  try {
    const parsed = JSON.parse(storage.getItem(reviewDraftKey(itemId)) || 'null')
    return {
      note: typeof parsed?.note === 'string' ? parsed.note : typeof parsed?.receipt === 'string' ? parsed.receipt : '',
    }
  } catch {
    return emptyReviewDraft()
  }
}

export function persistReviewDraft(itemId, draft, storage = globalThis.localStorage) {
  if (!itemId || !usableStorage(storage)) return
  storage.setItem(reviewDraftKey(itemId), JSON.stringify({
    note: String(draft?.note || ''),
  }))
}

export function clearReviewDraft(itemId, storage = globalThis.localStorage) {
  if (!itemId || !usableStorage(storage)) return
  storage.removeItem(reviewDraftKey(itemId))
}

export function hasReviewDraft(itemId, storage = globalThis.localStorage) {
  if (!itemId || !usableStorage(storage)) return false
  return storage.getItem(reviewDraftKey(itemId)) !== null
}

export function isReviewCardItem(item, storage = globalThis.localStorage) {
  return Boolean(item?.id && item.status === 'human_review')
}

export async function saveReviewNoteDraft({ itemId, draft, saveNote, storage = globalThis.localStorage }) {
  if (!itemId) throw new Error('Review item ID is required')
  persistReviewDraft(itemId, draft, storage)
  const response = await saveNote(itemId, { review_note: String(draft?.note || '') })
  if (response?.success === false || response?.ok === false) {
    throw new Error(response?.reason || response?.message || 'Review note save failed')
  }
  if (response?.status !== 'human_review' || response?.state_changed !== false) {
    throw new Error('Review note save changed item state unexpectedly')
  }
  clearReviewDraft(itemId, storage)
  return response
}

export async function applyReviewDecision({ itemId, decision, note, closeReview }) {
  const status = { approve: 'done', needs_changes: 'needs_input', block: 'blocked' }[decision]
  if (!status) throw new Error('Invalid review decision')
  if (status !== 'done' && !String(note || '').trim()) throw new Error('Needs changes and Block require a review note')
  const response = await closeReview(itemId, { status, review_note: String(note || ''), action: decision })
  if (response?.success === false || response?.ok === false) {
    throw new Error(response?.reason || response?.message || 'Review action failed')
  }
  return response
}
