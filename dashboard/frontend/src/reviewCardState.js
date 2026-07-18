export const REVIEW_CLOSE_STATUSES = ['done', 'needs_input', 'blocked']

const REVIEW_DRAFT_PREFIX = 'aos.dashboard.review-card.v1.'

export const reviewDraftKey = itemId => `${REVIEW_DRAFT_PREFIX}${itemId}`

const usableStorage = storage => storage && typeof storage.getItem === 'function'

export const emptyReviewDraft = () => ({ receipt: '', status: 'done' })

export function loadReviewDraft(itemId, storage = globalThis.localStorage) {
  if (!itemId || !usableStorage(storage)) return emptyReviewDraft()
  try {
    const parsed = JSON.parse(storage.getItem(reviewDraftKey(itemId)) || 'null')
    return {
      receipt: typeof parsed?.receipt === 'string' ? parsed.receipt : '',
      status: REVIEW_CLOSE_STATUSES.includes(parsed?.status) ? parsed.status : 'done',
    }
  } catch {
    return emptyReviewDraft()
  }
}

export function persistReviewDraft(itemId, draft, storage = globalThis.localStorage) {
  if (!itemId || !usableStorage(storage)) return
  storage.setItem(reviewDraftKey(itemId), JSON.stringify({
    receipt: String(draft?.receipt || ''),
    status: REVIEW_CLOSE_STATUSES.includes(draft?.status) ? draft.status : 'done',
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
  if (!item?.id) return false
  return item.status === 'human_review'
    || (['needs_input', 'blocked'].includes(item.status) && hasReviewDraft(item.id, storage))
}

export async function saveReviewDraft({ itemId, draft, closeReview, storage = globalThis.localStorage }) {
  if (!itemId) throw new Error('Review item ID is required')
  if (!REVIEW_CLOSE_STATUSES.includes(draft?.status)) throw new Error('Invalid review-close status')

  persistReviewDraft(itemId, draft, storage)
  const response = await closeReview(itemId, {
    status: draft.status,
    review_note: String(draft.receipt || ''),
  })
  if (response?.success === false || response?.ok === false) {
    throw new Error(response?.reason || response?.message || 'Review update failed')
  }
  if (draft.status === 'done') clearReviewDraft(itemId, storage)
  return response
}
