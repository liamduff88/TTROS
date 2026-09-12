export const ASK_DAVID_THREAD_STORAGE_KEY = 'aos.dashboard.david.thread.v1'
export const ASK_DAVID_DRAFT_STORAGE_KEY = 'aos.dashboard.david.draft.v1'

export function loadStoredThread(storage) {
  try {
    const raw = storage?.getItem(ASK_DAVID_THREAD_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function persistThread(storage, thread) {
  try {
    storage?.setItem(ASK_DAVID_THREAD_STORAGE_KEY, JSON.stringify(thread || []))
  } catch {
    // sessionStorage unavailable or full; visible history simply won't persist.
  }
}

export function loadStoredDraft(storage) {
  try {
    const raw = storage?.getItem(ASK_DAVID_DRAFT_STORAGE_KEY)
    return typeof raw === 'string' ? raw : ''
  } catch {
    return ''
  }
}

export function persistDraft(storage, draft) {
  try {
    if (draft) {
      storage?.setItem(ASK_DAVID_DRAFT_STORAGE_KEY, draft)
    } else {
      storage?.removeItem(ASK_DAVID_DRAFT_STORAGE_KEY)
    }
  } catch {
    // sessionStorage unavailable or full; the draft simply won't persist.
  }
}
