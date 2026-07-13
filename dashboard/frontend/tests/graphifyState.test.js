// Revisit: when Repo Ingest URL validation changes. · Last touched: 2026-07-13.
import test from 'node:test'
import assert from 'node:assert/strict'
import { validateGitHubRepositoryUrl } from '../src/graphifyState.js'

test('valid GitHub repository URLs normalize optional .git', () => {
  const plain = validateGitHubRepositoryUrl('https://github.com/pallets/itsdangerous')
  const dotted = validateGitHubRepositoryUrl('https://github.com/pallets/itsdangerous.git')
  assert.equal(plain.valid, true)
  assert.equal(dotted.valid, true)
  assert.equal(plain.normalized, dotted.normalized)
  assert.equal(plain.id, 'pallets/itsdangerous')
})

test('typing validation rejects prohibited URL classes without fetching', () => {
  const invalid = [
    'https://user:pass@github.com/owner/repo',
    'https://github.com/owner/repo?q=1',
    'https://github.com/owner/repo#x',
    'https://www.github.com/owner/repo',
    'ssh://github.com/owner/repo',
    'git@github.com:owner/repo',
    'git://github.com/owner/repo',
    'file:///tmp/repo',
    '/tmp/repo',
    'https://github.com:443/owner/repo',
    'https://github.com/owner/repo/extra',
    'https://github.com/owner/%2e%2e',
    'https://github.com/owner\\repo',
  ]
  for (const value of invalid) assert.equal(validateGitHubRepositoryUrl(value).valid, false, value)
})
