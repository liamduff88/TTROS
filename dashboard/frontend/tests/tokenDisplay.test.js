// Revisit: when token availability rendering changes. · Last touched: 2026-07-20.

import test from 'node:test'
import assert from 'node:assert/strict'

import { sourceComponentTotalText, tokenComponentText } from '../src/tokenDisplay.js'

test('unavailable token components render honestly and never as NaN', () => {
  assert.equal(tokenComponentText('unavailable from current CLI output', 'cached', ' separate'), 'cached unavailable')
  assert.equal(tokenComponentText(null, 'reasoning', ' ⊂ output'), 'reasoning unavailable')
  assert.equal(tokenComponentText(0, 'cached', ' separate'), '0 cached separate')
  assert.doesNotMatch(tokenComponentText('not-a-number', 'cached'), /NaN/)
})

test('source totals distinguish complete zero, complete totals, partial totals, and unavailable', () => {
  assert.equal(sourceComponentTotalText({ exact_rows: 1, cached_input: 0, cached_input_unavailable_rows: 0 }, 'cached_input', 'cached_input_unavailable_rows'), '0')
  assert.equal(sourceComponentTotalText({ exact_rows: 2, cached_input: 12, cached_input_unavailable_rows: 0 }, 'cached_input', 'cached_input_unavailable_rows'), '12')
  assert.equal(sourceComponentTotalText({ exact_rows: 2, cached_input: 12, cached_input_unavailable_rows: 1 }, 'cached_input', 'cached_input_unavailable_rows'), '12 known + 1 unavailable')
  assert.equal(sourceComponentTotalText({ exact_rows: 2, cached_input: 0, cached_input_unavailable_rows: 2 }, 'cached_input', 'cached_input_unavailable_rows'), 'unavailable')
})
