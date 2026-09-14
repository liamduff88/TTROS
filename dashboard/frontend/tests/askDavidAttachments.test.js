// Revisit: when David's attachment contract changes. · Created 2026-09-13.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = path => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const source = read('../src/components/AskDavid.jsx')

test('David has a real paperclip wired to the shared upload mechanism', () => {
  assert.match(source, /import \{ askDavid, uploadFile \} from '\.\.\/api'/)
  assert.match(source, /data-testid="ask-david-attach-button"/)
  assert.match(source, /data-testid="ask-david-file-input"/)
  assert.match(source, /await uploadFile\(file\)/)
})

test('an attachment is sent as an opaque upload_id reference, never a raw filesystem path', () => {
  assert.match(source, /attachments\.filter\(item => item\.upload_id\)\.map\(item => `upload:\$\{item\.upload_id\}`\)/)
  assert.match(source, /askDavid\(clean, attachmentRefs\)/)
})

test('sent attachments stay visibly associated with the message that carried them', () => {
  assert.match(source, /data-testid="ask-david-sent-attachments"/)
  assert.match(source, /entry\.attachments\?\.length > 0/)
})

test('a response that ingests into the Business Brain is rendered distinctly from an ordinary reply', () => {
  assert.match(source, /entry\.kind === 'memory_intake_ingested'/)
  assert.match(source, /data-testid="ask-david-ingested"/)
})

test('attaching a file alone never calls a memory-intake ingest endpoint from the frontend', () => {
  assert.doesNotMatch(source, /ingestMemoryIntake/)
})
