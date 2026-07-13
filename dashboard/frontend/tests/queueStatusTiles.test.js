import assert from 'node:assert/strict'
import test from 'node:test'

import { createServer } from 'vite'

const textContent = node => {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  const children = node.props?.children
  return Array.isArray(children) ? children.map(textContent).join('') : textContent(children)
}

test('status tile click sets and clears the filter while the chip stays in sync', async t => {
  const vite = await createServer({ appType: 'custom', logLevel: 'silent', server: { middlewareMode: true } })
  t.after(() => vite.close())
  const { CountTile, QueueFilterChip, toggleQueueStatusFilter } = await vite.ssrLoadModule('/src/views/Queue.jsx')

  let filters = {}
  const onToggle = status => { filters = toggleQueueStatusFilter(filters, status) }

  let tile = CountTile({ status: 'human_review', value: 3, active: false, onToggle })
  assert.equal(tile.type, 'button')
  assert.equal(tile.props['aria-pressed'], false)
  tile.props.onClick()

  assert.equal(filters.status, 'human_review')
  tile = CountTile({ status: 'human_review', value: 3, active: filters.status === 'human_review', onToggle })
  assert.equal(tile.props['aria-pressed'], true)
  assert.match(tile.props.className, /border-champagne\/40/)
  assert.equal(textContent(QueueFilterChip({ filters, onClear: () => {} })), 'Filtered: human review ×')

  tile.props.onClick()

  assert.equal(filters.status, undefined)
  assert.equal(QueueFilterChip({ filters, onClear: () => {} }), null)
})
