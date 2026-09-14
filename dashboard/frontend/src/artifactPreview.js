// Pure, dependency-free helpers for the internal artifact viewer tabs.
// Kept free of React/DOM so the parsing rules are unit-testable on their own.

export const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'])
export const PDF_EXTENSIONS = new Set(['.pdf'])
export const MARKDOWN_EXTENSIONS = new Set(['.md'])

export const artifactKind = extension => {
  const value = String(extension || '').toLowerCase()
  if (IMAGE_EXTENSIONS.has(value)) return 'image'
  if (PDF_EXTENSIONS.has(value)) return 'pdf'
  if (MARKDOWN_EXTENSIONS.has(value)) return 'markdown'
  return 'text'
}

// Human label for a tab / primary-result button. Prefers a real deliverable
// name over a generic "Open Result" when one can be safely derived.
export const artifactTabLabel = ref => {
  const name = String(ref?.name || ref?.path || '').split('/').pop() || 'Artifact'
  const base = name.replace(/\.[^./]+$/, '').replace(/[_-]+/g, ' ').trim()
  if (!base) return name
  return base.replace(/\b\w/g, char => char.toUpperCase())
}

export const primaryResultButtonLabel = ref => {
  if (!ref?.path) return 'Open Result'
  const label = artifactTabLabel(ref)
  return label ? `Open ${label}` : 'Open Result'
}

const HEADING_RE = /^(#{1,6})\s+(.*)$/
const UL_RE = /^\s*[-*]\s+(.*)$/
const OL_RE = /^\s*\d+[.)]\s+(.*)$/
const FENCE_RE = /^```/
const HR_RE = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/
const TABLE_ROW_RE = /^\s*\|(.+)\|\s*$/
const TABLE_SEPARATOR_RE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/

const splitTableRow = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim())

// Parses a restricted, safe subset of Markdown into block descriptors.
// Returns data only (no HTML/JSX) so callers render it however they need to.
export function parseMarkdownBlocks(text) {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let index = 0
  let paragraph = []

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: 'paragraph', text: paragraph.join(' ').trim() })
      paragraph = []
    }
  }

  while (index < lines.length) {
    const line = lines[index]

    if (FENCE_RE.test(line)) {
      flushParagraph()
      const codeLines = []
      index += 1
      while (index < lines.length && !FENCE_RE.test(lines[index])) {
        codeLines.push(lines[index])
        index += 1
      }
      index += 1 // skip closing fence
      blocks.push({ type: 'code', text: codeLines.join('\n') })
      continue
    }

    if (HR_RE.test(line)) {
      flushParagraph()
      blocks.push({ type: 'hr' })
      index += 1
      continue
    }

    if (TABLE_ROW_RE.test(line) && lines[index + 1] !== undefined && TABLE_SEPARATOR_RE.test(lines[index + 1])) {
      flushParagraph()
      const header = splitTableRow(line)
      index += 2
      const rows = []
      while (index < lines.length && TABLE_ROW_RE.test(lines[index])) {
        rows.push(splitTableRow(lines[index]))
        index += 1
      }
      blocks.push({ type: 'table', header, rows })
      continue
    }

    const heading = line.match(HEADING_RE)
    if (heading) {
      flushParagraph()
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2].trim() })
      index += 1
      continue
    }

    if (UL_RE.test(line) || OL_RE.test(line)) {
      flushParagraph()
      const ordered = OL_RE.test(line)
      const items = []
      while (index < lines.length) {
        const match = lines[index].match(ordered ? OL_RE : UL_RE)
        if (!match) break
        items.push(match[1].trim())
        index += 1
      }
      blocks.push({ type: 'list', ordered, items })
      continue
    }

    if (!line.trim()) {
      flushParagraph()
      index += 1
      continue
    }

    paragraph.push(line.trim())
    index += 1
  }
  flushParagraph()
  return blocks
}

const INLINE_RE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/

// Tokenizes inline text into plain data tokens: {type:'text'|'bold'|'italic'|'code'|'link', value, href?}
export function parseInlineMarkdown(text) {
  const value = String(text || '')
  if (!value) return []
  const tokens = []
  let remaining = value
  while (remaining) {
    const match = remaining.match(INLINE_RE)
    if (!match) {
      tokens.push({ type: 'text', value: remaining })
      break
    }
    const before = remaining.slice(0, match.index)
    if (before) tokens.push({ type: 'text', value: before })
    const chunk = match[0]
    if (chunk.startsWith('**')) {
      tokens.push({ type: 'bold', value: chunk.slice(2, -2) })
    } else if (chunk.startsWith('`')) {
      tokens.push({ type: 'code', value: chunk.slice(1, -1) })
    } else if (chunk.startsWith('[')) {
      const linkMatch = chunk.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
      tokens.push({ type: 'link', value: linkMatch?.[1] || chunk, href: linkMatch?.[2] || '' })
    } else if (chunk.startsWith('*')) {
      tokens.push({ type: 'italic', value: chunk.slice(1, -1) })
    } else {
      tokens.push({ type: 'text', value: chunk })
    }
    remaining = remaining.slice(match.index + chunk.length)
  }
  return tokens
}

// Derives an in-view outline from a parsed document's H2/H3 headings. Ids are
// index-based (not slugged from text) so they are always unique and always
// match whatever heading the renderer assigns the same id to, with no risk of
// collisions between same-titled sections.
export function extractHeadingOutline(blocks) {
  return (Array.isArray(blocks) ? blocks : [])
    .map((block, index) => ({ block, index }))
    .filter(({ block }) => block.type === 'heading' && (block.level === 2 || block.level === 3))
    .map(({ block, index }) => ({ id: `md-heading-${index}`, level: block.level, text: block.text }))
}

const NUMBERED_HEADING_RE = /^\d+[.)]\s*(.+)$/

// Generic "repeated structured entity" extraction (e.g. selected outreach
// candidates, a numbered list of findings): finds a heading followed by a run
// of directly-nested numbered sub-headings, anywhere before the next heading
// of equal-or-higher level, and reports how many there are plus a short label
// for each. Deliberately shape-driven (numbered sub-heading directly under a
// section), not tied to any one workflow's wording, so it generalizes to any
// report that follows this common "## Selected X" / "### 1. Name" convention.
// The anchor is required to be level 2+: a document's own H1 title is never a
// "section", and without this a real report (H1 title, then several H2
// sections deeper in the document) would match on the H1 and vacuum up every
// numbered sub-heading in the whole file instead of the intended section's.
export function extractRepeatedEntitySummary(blocks) {
  const list = Array.isArray(blocks) ? blocks : []
  for (let i = 0; i < list.length; i += 1) {
    const heading = list[i]
    if (heading.type !== 'heading' || heading.level < 2) continue
    const entries = []
    for (let j = i + 1; j < list.length; j += 1) {
      const next = list[j]
      if (next.type !== 'heading') continue
      if (next.level <= heading.level) break
      if (next.level !== heading.level + 1) continue
      const match = next.text.match(NUMBERED_HEADING_RE)
      if (match) entries.push(match[1].trim())
    }
    if (entries.length >= 2) return { heading: heading.text, count: entries.length, names: entries.slice(0, 8) }
  }
  return null
}

const NO_EXTERNAL_ACTION_RE = /no external action (?:was )?taken|zero sends?:\s*confirmed/i

// Generic no-send/no-external-action state detection, matching the repo-wide
// "no external action was taken" / "zero sends: confirmed" convention used
// across TTROS workflow receipts and reports rather than any one workflow.
export const detectNoExternalAction = text => NO_EXTERNAL_ACTION_RE.test(String(text || ''))

// Section headings that carry safety/verification/receipt bookkeeping rather
// than the business result itself (F-REPORT-PRIORITY). Shape-driven generic
// wording, not one workflow's exact heading text, so it demotes the same kind
// of section in any TTROS workflow report. Matched against H2 heading text.
const DEMOTED_SECTION_RE = /approval|safety gate|verification checks?|receipt block|blocked external action/i

// Splits a parsed document into top-level (H2-bounded) sections for display,
// marking which ones are safety/verification/receipt bookkeeping so a
// renderer can collapse them by default without deleting or reordering any
// source content — every block keeps its original flat index so heading ids
// stay stable and match extractHeadingOutline. A document with no H2 headings
// at all (or content before the first one) comes back as one non-demoted
// section so nothing is ever silently dropped.
export function groupMarkdownSections(blocks) {
  const list = Array.isArray(blocks) ? blocks : []
  const sections = []
  let current = null
  list.forEach((block, index) => {
    if (block.type === 'heading' && block.level === 2) {
      current = { heading: block, headingIndex: index, entries: [], demoted: DEMOTED_SECTION_RE.test(block.text) }
      sections.push(current)
      return
    }
    if (!current) {
      current = { heading: null, headingIndex: -1, entries: [], demoted: false }
      sections.push(current)
    }
    current.entries.push({ block, index })
  })
  return sections
}
