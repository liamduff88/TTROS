// Revisit: when permanent Executive Team membership or consultation states change. · Last touched: 2026-08-07.
// 'hermes'/operator-lean was removed from this optional specialist list: David is now the
// primary executive conversation partner and already covers that daily-judgment remit.

export const EXECUTIVE_TEAM_MEMBERS = Object.freeze([
  { id: 'revenue', name: 'Revenue', profile: 'aos-revenue', remit: 'Offers, pipeline and commercial action' },
  { id: 'marketing', name: 'Marketing', profile: 'aos-marketing', remit: 'Campaigns, positioning and demand' },
  { id: 'delivery', name: 'Delivery', profile: 'aos-delivery', remit: 'Client onboarding and execution' },
  { id: 'operations', name: 'Operations', profile: 'aos-ops', remit: 'Priorities, blockers and operating health' },
  { id: 'executive-team', name: 'Executive Team', profile: 'aos-orchestrator', remit: 'Cross-department coordination' },
])

export const initialExecutiveConsultation = Object.freeze({
  status: 'idle',
  result: null,
  error: null,
})

export function executiveConsultationReducer(state, action) {
  if (action.type === 'reset') return { ...initialExecutiveConsultation }
  if (action.type === 'start') return { status: 'loading', result: null, error: null }
  if (action.type === 'success') return { status: 'success', result: action.result, error: null }
  if (action.type === 'failure') return { status: 'failure', result: action.result || null, error: action.error }
  return state
}

export const canSubmitExecutiveConsultation = (state, text) => state.status !== 'loading' && Boolean(String(text || '').trim())

export function executiveApiError(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail?.error?.message) return detail.error.message
  if (detail?.message) return detail.message
  if (error?.code === 'ECONNABORTED') return 'Invocation timed out in the dashboard. Retry uses the same request ID so a completed response is replayed safely.'
  if (error?.response?.status === 404) return 'Executive consultation route is missing from the backend.'
  if (!error?.response) return 'Dashboard backend is unavailable or disconnected.'
  return error?.message || 'Executive consultation failed.'
}
