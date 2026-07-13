export const HUMAN_NEEDED_STATUSES = new Set(['human_review', 'needs_input', 'blocked'])

export const normalizedStatus = value => String(value || '').trim().toLowerCase()

export const humanNeededItems = items => (Array.isArray(items) ? items : [])
  .filter(item => HUMAN_NEEDED_STATUSES.has(normalizedStatus(item?.status)))

export function normalizeCockpitQueue(cockpit) {
  if (!cockpit || cockpit.error) return cockpit
  const source = Array.isArray(cockpit.queue_items) ? cockpit.queue_items : cockpit.needs_me
  const needsMe = humanNeededItems(source)
  return {
    ...cockpit,
    needs_me: needsMe,
    needs_me_count: needsMe.length,
    human_needed_count: needsMe.length,
  }
}

export function mergeQueueSummary(cockpit, summary) {
  if (!summary || summary.success === false) return cockpit
  const needsMe = humanNeededItems(summary.needsMeItems)
  return {
    ...(cockpit && !cockpit.error ? cockpit : {}),
    counts: summary.counts || cockpit?.counts || {},
    needs_me: needsMe,
    needs_me_count: needsMe.length,
    human_needed_count: needsMe.length,
    queueSummaryLoaded: true,
  }
}

export function resolveQueueSelection({ items, currentId, preferredId, nextId, selectionChanged = false }) {
  const list = Array.isArray(items) ? items : []
  const exists = id => Boolean(id) && list.some(item => item.id === id)
  if (selectionChanged && exists(currentId)) return currentId
  if (exists(preferredId)) return preferredId
  if (exists(currentId)) return currentId
  if (exists(nextId)) return nextId
  return list[0]?.id || null
}
