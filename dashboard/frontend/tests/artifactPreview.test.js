import assert from 'node:assert/strict'
import test from 'node:test'
import {
  artifactKind,
  artifactTabLabel,
  detectNoExternalAction,
  extractHeadingOutline,
  extractRepeatedEntitySummary,
  parseInlineMarkdown,
  parseMarkdownBlocks,
  primaryResultButtonLabel,
} from '../src/artifactPreview.js'

test('artifactKind classifies known extensions and falls back to text', () => {
  assert.equal(artifactKind('.png'), 'image')
  assert.equal(artifactKind('.PDF'), 'pdf')
  assert.equal(artifactKind('.md'), 'markdown')
  assert.equal(artifactKind('.jsonl'), 'text')
  assert.equal(artifactKind(''), 'text')
})

test('artifactTabLabel derives a readable name from a file path', () => {
  assert.equal(artifactTabLabel({ path: 'workflows/queue_artifacts/AOS-1_outreach_report.md' }), 'AOS 1 Outreach Report')
  assert.equal(artifactTabLabel({ name: 'final-review-package.md' }), 'Final Review Package')
  assert.equal(artifactTabLabel(null), 'Artifact')
})

test('primaryResultButtonLabel prefers a specific label over the generic default', () => {
  assert.equal(primaryResultButtonLabel({ path: 'results/outreach_report.md', name: 'outreach_report.md' }), 'Open Outreach Report')
  assert.equal(primaryResultButtonLabel(null), 'Open Result')
  assert.equal(primaryResultButtonLabel({}), 'Open Result')
})

test('parseMarkdownBlocks separates headings, paragraphs, lists, code, and rules', () => {
  const text = [
    '# Title',
    '',
    'A paragraph line one',
    'continued on line two',
    '',
    '- item one',
    '- item two',
    '',
    '```',
    'code line',
    '```',
    '',
    '---',
  ].join('\n')
  const blocks = parseMarkdownBlocks(text)
  assert.deepEqual(blocks[0], { type: 'heading', level: 1, text: 'Title' })
  assert.deepEqual(blocks[1], { type: 'paragraph', text: 'A paragraph line one continued on line two' })
  assert.deepEqual(blocks[2], { type: 'list', ordered: false, items: ['item one', 'item two'] })
  assert.deepEqual(blocks[3], { type: 'code', text: 'code line' })
  assert.deepEqual(blocks[4], { type: 'hr' })
})

test('parseMarkdownBlocks handles ordered lists distinctly from unordered lists', () => {
  const blocks = parseMarkdownBlocks('1. first\n2. second')
  assert.deepEqual(blocks[0], { type: 'list', ordered: true, items: ['first', 'second'] })
})

test('parseInlineMarkdown tokenizes bold, italic, code, and links without dropping surrounding text', () => {
  const tokens = parseInlineMarkdown('see **bold** and `code` and [a link](https://example.com) plain')
  assert.deepEqual(tokens, [
    { type: 'text', value: 'see ' },
    { type: 'bold', value: 'bold' },
    { type: 'text', value: ' and ' },
    { type: 'code', value: 'code' },
    { type: 'text', value: ' and ' },
    { type: 'link', value: 'a link', href: 'https://example.com' },
    { type: 'text', value: ' plain' },
  ])
})

test('parseInlineMarkdown returns a single text token for plain text', () => {
  assert.deepEqual(parseInlineMarkdown('plain text'), [{ type: 'text', value: 'plain text' }])
  assert.deepEqual(parseInlineMarkdown(''), [])
})

test('parseMarkdownBlocks parses a GFM pipe table into header and rows', () => {
  const text = ['| Name | Score |', '| --- | --- |', '| Nicolas | 94 |', '| Parminder | 94 |'].join('\n')
  const blocks = parseMarkdownBlocks(text)
  assert.deepEqual(blocks[0], {
    type: 'table',
    header: ['Name', 'Score'],
    rows: [['Nicolas', '94'], ['Parminder', '94']],
  })
})

test('extractHeadingOutline keeps only H2/H3 headings with stable, unique ids', () => {
  const blocks = parseMarkdownBlocks(['# Title', '## Selected outreach candidates', '### 1. First', 'body', '#### too deep'].join('\n'))
  const outline = extractHeadingOutline(blocks)
  assert.deepEqual(outline, [
    { id: 'md-heading-1', level: 2, text: 'Selected outreach candidates' },
    { id: 'md-heading-2', level: 3, text: '1. First' },
  ])
})

test('extractRepeatedEntitySummary finds a numbered sub-heading section generically', () => {
  const text = [
    '## Selected outreach candidates',
    'Selected N=5 from existing local evidence.',
    '### 1. Nicolas Dupont — Cyborg',
    'body text for candidate one',
    '### 2. Parminder Singh — DeepInspect.AI',
    'body text for candidate two',
    '## Next section',
  ].join('\n')
  const result = extractRepeatedEntitySummary(parseMarkdownBlocks(text))
  assert.equal(result.heading, 'Selected outreach candidates')
  assert.equal(result.count, 2)
  assert.deepEqual(result.names, ['Nicolas Dupont — Cyborg', 'Parminder Singh — DeepInspect.AI'])
})

test('extractRepeatedEntitySummary returns null when there is no repeated structure', () => {
  assert.equal(extractRepeatedEntitySummary(parseMarkdownBlocks('# Title\n\njust a paragraph')), null)
})

test('extractRepeatedEntitySummary anchors on the real section, not the document H1 title', () => {
  // Every real workflow report (workflows/queue_artifacts/*.md) starts with an
  // H1 title before its H2 sections; a candidate-selected section is real
  // content while other numbered headings elsewhere in the document are not.
  const text = [
    '# AOS-2026-0498 — Internal Outreach Daily local no-send review package',
    '',
    'Run timestamp: 2026-09-12T01:55:13Z',
    '',
    '## Approval and safety gates preserved',
    '',
    '- Zero sends: confirmed.',
    '',
    '## Selected outreach candidates',
    '',
    'Selected N=5 from existing local evidence.',
    '### 1. Nicolas Dupont — Cyborg',
    'body text for candidate one',
    '### 2. Parminder Singh — DeepInspect.AI',
    'body text for candidate two',
    '',
    '## Reviewed but not selected today',
    '',
    '- Loretta Davis — Talent Harbour Group: historical review account.',
  ].join('\n')
  const result = extractRepeatedEntitySummary(parseMarkdownBlocks(text))
  assert.equal(result.heading, 'Selected outreach candidates')
  assert.equal(result.count, 2)
  assert.deepEqual(result.names, ['Nicolas Dupont — Cyborg', 'Parminder Singh — DeepInspect.AI'])
})

test('detectNoExternalAction matches the repo-wide no-send convention', () => {
  assert.equal(detectNoExternalAction('No external action was taken.'), true)
  assert.equal(detectNoExternalAction('Zero sends: confirmed.'), true)
  assert.equal(detectNoExternalAction('The email was sent.'), false)
})
