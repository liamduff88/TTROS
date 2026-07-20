// Revisit: when the dashboard token response contract changes. · Last touched: 2026-07-20.

const availableTokenNumber = value => {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) return value
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value)
  return null
}

export const tokenComponentText = (value, label, suffix = '') => {
  const available = availableTokenNumber(value)
  return available === null
    ? `${label} unavailable`
    : `${available.toLocaleString()} ${label}${suffix}`
}

export const sourceComponentTotalText = (group, totalKey, unavailableRowsKey) => {
  const total = availableTokenNumber(group?.[totalKey])
  const exactRows = availableTokenNumber(group?.exact_rows) || 0
  const unavailableRows = availableTokenNumber(group?.[unavailableRowsKey]) || 0
  if (total === null || exactRows === 0 || unavailableRows >= exactRows) return 'unavailable'
  return unavailableRows > 0
    ? `${total.toLocaleString()} known + ${unavailableRows.toLocaleString()} unavailable`
    : total.toLocaleString()
}
