import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ASK_DAVID_DRAFT_STORAGE_KEY,
  ASK_DAVID_THREAD_STORAGE_KEY,
  loadStoredDraft,
  loadStoredThread,
  persistDraft,
  persistThread,
} from '../src/askDavidState.js'

function fakeStorage(initial = {}) {
  const data = { ...initial }
  return {
    getItem: key => (key in data ? data[key] : null),
    setItem: (key, value) => { data[key] = value },
    removeItem: key => { delete data[key] },
    _data: data,
  }
}

test('missing or absent storage yields an empty thread, never a crash', () => {
  assert.deepEqual(loadStoredThread(fakeStorage()), [])
  assert.deepEqual(loadStoredThread(undefined), [])
})

test('corrupt or non-array persisted content is rejected back to an empty thread', () => {
  assert.deepEqual(loadStoredThread(fakeStorage({ [ASK_DAVID_THREAD_STORAGE_KEY]: 'not json' })), [])
  assert.deepEqual(loadStoredThread(fakeStorage({ [ASK_DAVID_THREAD_STORAGE_KEY]: JSON.stringify({ not: 'an array' }) })), [])
})

test('a persisted thread round-trips through load exactly', () => {
  const storage = fakeStorage()
  const thread = [{ id: '1', type: 'user', text: 'hello' }, { id: '2', type: 'reply', kind: 'david_reply', success: true, response: 'hi' }]
  persistThread(storage, thread)
  assert.deepEqual(loadStoredThread(storage), thread)
})

test('persistThread never throws even when storage is unavailable or full', () => {
  const throwingStorage = { setItem: () => { throw new Error('quota exceeded') } }
  assert.doesNotThrow(() => persistThread(throwingStorage, [{ id: '1' }]))
  assert.doesNotThrow(() => persistThread(undefined, [{ id: '1' }]))
})

test('an empty thread persists and reloads as empty, not as a stale prior entry', () => {
  const storage = fakeStorage({ [ASK_DAVID_THREAD_STORAGE_KEY]: JSON.stringify([{ id: 'stale' }]) })
  persistThread(storage, [])
  assert.deepEqual(loadStoredThread(storage), [])
})

test('missing or absent storage yields an empty draft, never a crash', () => {
  assert.equal(loadStoredDraft(fakeStorage()), '')
  assert.equal(loadStoredDraft(undefined), '')
})

test('a persisted draft round-trips through load exactly', () => {
  const storage = fakeStorage()
  persistDraft(storage, 'unsent text')
  assert.equal(loadStoredDraft(storage), 'unsent text')
})

test('clearing a draft removes it from storage rather than persisting an empty string', () => {
  const storage = fakeStorage({ [ASK_DAVID_DRAFT_STORAGE_KEY]: 'stale draft' })
  persistDraft(storage, '')
  assert.equal(loadStoredDraft(storage), '')
  assert.equal(ASK_DAVID_DRAFT_STORAGE_KEY in storage._data, false)
})

test('persistDraft never throws even when storage is unavailable or full', () => {
  const throwingStorage = { setItem: () => { throw new Error('quota exceeded') }, removeItem: () => { throw new Error('nope') } }
  assert.doesNotThrow(() => persistDraft(throwingStorage, 'x'))
  assert.doesNotThrow(() => persistDraft(undefined, 'x'))
})

test('AskDavid hydrates thread and draft from storage on mount, persists on change, clears draft on send, and never resends history to the model', async () => {
  const source = await import('node:fs/promises').then(fs => fs.readFile(new URL('../src/components/AskDavid.jsx', import.meta.url), 'utf8'))
  assert.match(source, /loadStoredThread\(window\.sessionStorage\)/)
  assert.match(source, /persistThread\(window\.sessionStorage, thread\)/)
  assert.match(source, /loadStoredDraft\(window\.sessionStorage\)/)
  assert.match(source, /persistDraft\(window\.sessionStorage, text\)/)
  assert.match(source, /askDavid\(clean, attachmentRefs\)/)
  assert.doesNotMatch(source, /askDavid\([^)]*thread/)
  assert.match(source, /setText\(''\)/)
})
