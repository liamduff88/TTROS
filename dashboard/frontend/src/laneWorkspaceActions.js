export const REVIEW_ACTIONS = [
  { id: 'approve', label: 'Approve' },
  { id: 'needs_changes', label: 'Needs changes' },
  { id: 'reject', label: 'Reject' },
]

const READY_STATUSES = new Set(['inbox', 'agent_todo'])
const REVIEW_STATUSES = new Set(['human_review', 'needs_input'])

const ensureSuccess = result => {
  if (result?.success === false || result?.ok === false) {
    throw new Error(result?.reason || result?.message || 'Queue action failed')
  }
  return result
}

export const isLaneSelectable = item => READY_STATUSES.has(String(item?.status || '').toLowerCase())

export const selectedLaneItems = (items, selectedIds) => {
  const selected = new Set(Array.isArray(selectedIds) ? selectedIds : [])
  return (Array.isArray(items) ? items : []).filter(item => selected.has(item.id) && isLaneSelectable(item))
}

export const cancellationReceiptText = item => [
  'PASS',
  '',
  'Queue cancellation:',
  `- Work item: ${item.id}`,
  '- Action: Cancelled from the lane workspace.',
  '- Token usage: no agent invocation',
].join('\n')

const inputActionReceiptText = (item, action, note) => [
  'PASS',
  '',
  'Operator lane action:',
  `- Work item: ${item.id}`,
  `- Action: ${REVIEW_ACTIONS.find(candidate => candidate.id === action)?.label || action}`,
  `- Operator note: ${String(note || '').trim() || '(none)'}`,
  '- Token usage: no agent invocation',
].join('\n')

export const reviewActionNeedsNote = (item, action) =>
  item?.status === 'needs_input' || action === 'needs_changes' || action === 'reject'

export async function performReviewAction(item, action, note, endpoints) {
  if (!REVIEW_STATUSES.has(item?.status)) throw new Error('Review actions require a human_review or needs_input item')
  if (!REVIEW_ACTIONS.some(candidate => candidate.id === action)) throw new Error('Unknown review action')
  const reviewNote = String(note || '').trim()
  if (reviewActionNeedsNote(item, action) && !reviewNote) throw new Error('Add an operator note before taking this action')

  if (item.status === 'human_review') {
    const status = { approve: 'done', needs_changes: 'needs_input', reject: 'blocked' }[action]
    return ensureSuccess(await endpoints.closeReview(item.id, { status, review_note: reviewNote, action }))
  }

  const status = { approve: 'agent_todo', needs_changes: 'needs_input', reject: 'blocked' }[action]
  return ensureSuccess(await endpoints.attachReceipt(item.id, {
    receipt_text: inputActionReceiptText(item, action, reviewNote),
    status,
  }))
}

export async function performReadyAction(item, action, endpoints) {
  if (!isLaneSelectable(item)) throw new Error('Run and cancel require an inbox or agent_todo item')
  if (action === 'run') return ensureSuccess(await endpoints.runItem(item.id))
  if (action === 'cancel') {
    return ensureSuccess(await endpoints.attachReceipt(item.id, {
      receipt_text: cancellationReceiptText(item),
      status: 'cancelled',
    }))
  }
  throw new Error('Unknown ready-item action')
}

export async function performSelectedAction(items, action, endpoints) {
  const results = []
  for (const item of items) {
    try {
      const result = await performReadyAction(item, action, endpoints)
      results.push({ id: item.id, success: true, result })
    } catch (error) {
      results.push({ id: item.id, success: false, error })
    }
  }
  return results
}

export async function unblockLaneItem(item, updateStatus) {
  if (item?.status !== 'blocked') throw new Error('Only blocked items can be unblocked')
  return ensureSuccess(await updateStatus(item.id, 'agent_todo'))
}
