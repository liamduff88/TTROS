import { LANE_ROUTE_NAMES } from './shellState.js'

export const LANE_FILTERS = [
  { id: 'needs_me', label: 'Needs Me' },
  { id: 'to_run', label: 'To Run' },
  { id: 'blocked', label: 'Blocked' },
  { id: 'all_active', label: 'All Active' },
  { id: 'done', label: 'Done' },
  { id: 'cancelled', label: 'Cancelled' },
]

const NEEDS_ME_STATUSES = new Set(['human_review', 'needs_input'])
const TO_RUN_STATUSES = new Set(['inbox', 'agent_todo'])
const TERMINAL_STATUSES = new Set(['done', 'cancelled'])
const FILTER_IDS = new Set(LANE_FILTERS.map(filter => filter.id))

export const normalizeLane = value => {
  const lane = String(value || '').trim().toLowerCase()
  const expanded = lane === 'ops' ? 'operations' : lane
  return LANE_ROUTE_NAMES.includes(expanded) ? expanded : null
}

export const queueItemLane = item => {
  const tag = (Array.isArray(item?.tags) ? item.tags : []).find(value => String(value).toLowerCase().startsWith('lane:'))
  const candidates = [tag ? String(tag).slice(5) : null, item?.lane, item?.owner]
  return candidates.map(normalizeLane).find(Boolean) || 'unassigned'
}

export const laneScopedItems = (items, lane) => {
  const normalizedLane = normalizeLane(lane)
  if (!normalizedLane) return []
  return (Array.isArray(items) ? items : []).filter(item => queueItemLane(item) === normalizedLane)
}

export const matchesLaneFilter = (item, filter) => {
  const status = String(item?.status || '').toLowerCase()
  if (filter === 'needs_me') return NEEDS_ME_STATUSES.has(status)
  if (filter === 'to_run') return TO_RUN_STATUSES.has(status)
  if (filter === 'blocked') return status === 'blocked'
  if (filter === 'done') return status === 'done'
  if (filter === 'cancelled') return status === 'cancelled'
  return !TERMINAL_STATUSES.has(status)
}

export const laneFilterCounts = items => Object.fromEntries(
  LANE_FILTERS.map(filter => [filter.id, items.filter(item => matchesLaneFilter(item, filter.id)).length]),
)

export const defaultLaneFilter = items =>
  items.some(item => matchesLaneFilter(item, 'needs_me')) ? 'needs_me' : 'all_active'

const timestampValue = value => {
  const timestamp = Date.parse(value || '')
  return Number.isNaN(timestamp) ? 0 : timestamp
}

const laneSortGroup = item => {
  if (matchesLaneFilter(item, 'needs_me')) return 0
  if (matchesLaneFilter(item, 'to_run')) return 1
  if (matchesLaneFilter(item, 'blocked')) return 2
  return 3
}

export const sortLaneItems = items => [...items].sort((left, right) => {
  const groupDifference = laneSortGroup(left) - laneSortGroup(right)
  if (groupDifference) return groupDifference
  const updatedDifference = timestampValue(right.updated_at) - timestampValue(left.updated_at)
  if (updatedDifference) return updatedDifference
  const createdDifference = timestampValue(right.created_at) - timestampValue(left.created_at)
  if (createdDifference) return createdDifference
  return String(right.id || '').localeCompare(String(left.id || ''))
})

export const buildLaneWorkspace = (items, lane, requestedFilter = null) => {
  const scopedItems = laneScopedItems(items, lane)
  const activeFilter = FILTER_IDS.has(requestedFilter) ? requestedFilter : defaultLaneFilter(scopedItems)
  return {
    lane: normalizeLane(lane),
    activeFilter,
    counts: laneFilterCounts(scopedItems),
    items: sortLaneItems(scopedItems.filter(item => matchesLaneFilter(item, activeFilter))),
    total: scopedItems.length,
  }
}
