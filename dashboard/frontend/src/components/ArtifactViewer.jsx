import { Fragment, useMemo } from 'react'
import { Clipboard } from 'lucide-react'
import { artifactKind, detectNoExternalAction, extractHeadingOutline, extractRepeatedEntitySummary, groupMarkdownSections, parseInlineMarkdown, parseMarkdownBlocks } from '../artifactPreview'

const InlineMarkdown = ({ text }) => (
  <>
    {parseInlineMarkdown(text).map((token, index) => {
      const key = `${token.type}-${index}`
      if (token.type === 'bold') return <strong key={key} className="font-semibold text-ivory">{token.value}</strong>
      if (token.type === 'italic') return <em key={key}>{token.value}</em>
      if (token.type === 'code') return <code key={key} className="rounded bg-softgraph px-1 py-0.5 font-mono text-[0.85em] text-champagne">{token.value}</code>
      if (token.type === 'link') return <a key={key} href={token.href} target="_blank" rel="noreferrer" className="text-champagne underline hover:text-stone">{token.value}</a>
      return <span key={key}>{token.value}</span>
    })}
  </>
)

// Headings get progressively stronger hierarchy so a long report scans
// easily; H2s get a top rule so major sections read as clearly separated.
const HEADING_CLASSES = {
  1: 'text-2xl font-bold text-ivory mt-2 mb-3',
  2: 'text-xl font-semibold text-ivory mt-7 mb-2 border-t border-softgraph pt-4',
  3: 'text-sm font-semibold uppercase tracking-wide text-champagne mt-5 mb-1.5',
}

const NUMBERED_ENTITY_RE = /^(\d+)[.)]\s*(.*)$/

// Renders a single parsed block. Shared between top-level sections and the
// contents of a demoted (collapsed-by-default) section so both paths produce
// identical output for the same block.
const renderMarkdownBlock = (block, index) => {
  const key = `${block.type}-${index}`
  const headingId = `md-heading-${index}`
  if (block.type === 'heading') {
    // A numbered H3 under a "selected/found X" section (e.g. an outreach
    // candidate) gets a distinct card treatment instead of blending into
    // plain heading text, so a list of entities is easy to scan without
    // changing the underlying report content.
    const numbered = block.level === 3 ? block.text.match(NUMBERED_ENTITY_RE) : null
    if (numbered) {
      return (
        <div key={key} id={headingId} className="mt-5 flex scroll-mt-24 items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-champagne text-xs font-bold text-ivory">{numbered[1]}</span>
          <span className="text-base font-semibold text-ivory"><InlineMarkdown text={numbered[2]} /></span>
        </div>
      )
    }
    return (
      <div key={key} id={headingId} className={`scroll-mt-24 ${HEADING_CLASSES[block.level] || 'text-sm font-semibold text-ivory mt-3 mb-1.5'}`}>
        <InlineMarkdown text={block.text} />
      </div>
    )
  }
  if (block.type === 'list') {
    const Tag = block.ordered ? 'ol' : 'ul'
    return (
      <Tag key={key} className={`ml-5 space-y-1.5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}>
        {block.items.map((item, itemIndex) => <li key={itemIndex}><InlineMarkdown text={item} /></li>)}
      </Tag>
    )
  }
  if (block.type === 'table') {
    return (
      <div key={key} className="overflow-x-auto rounded border border-softgraph">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-softgraph bg-ink">
              {block.header.map((cell, cellIndex) => (
                <th key={cellIndex} className="px-3 py-2 font-semibold text-ivory"><InlineMarkdown text={cell} /></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-softgraph/50 last:border-b-0">
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="px-3 py-2 align-top text-stone"><InlineMarkdown text={cell} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (block.type === 'code') {
    return <pre key={key} className="overflow-auto rounded border border-softgraph bg-ink px-3 py-2 font-mono text-xs text-stone">{block.text}</pre>
  }
  if (block.type === 'hr') return <hr key={key} className="border-softgraph" />
  return <p key={key}><InlineMarkdown text={block.text} /></p>
}

// Safety/verification/receipt bookkeeping sections stay in the document and
// in the outline, but render collapsed by default so the business result is
// what a reader hits first (F-REPORT-PRIORITY) — nothing is removed, just
// deprioritized visually.
export const MarkdownPreview = ({ blocks }) => {
  if (!blocks?.length) return <div className="text-sm text-taupe">File is empty.</div>
  const sections = groupMarkdownSections(blocks)
  return (
    <div className="space-y-3 text-[15px] leading-7 text-stone">
      {sections.map((section, sectionIndex) => {
        if (!section.heading) {
          return <Fragment key={`section-${sectionIndex}`}>{section.entries.map(({ block, index }) => renderMarkdownBlock(block, index))}</Fragment>
        }
        const headingId = `md-heading-${section.headingIndex}`
        if (!section.demoted) {
          return (
            <Fragment key={`section-${sectionIndex}`}>
              {renderMarkdownBlock(section.heading, section.headingIndex)}
              {section.entries.map(({ block, index }) => renderMarkdownBlock(block, index))}
            </Fragment>
          )
        }
        return (
          <details key={`section-${sectionIndex}`} id={headingId} className="scroll-mt-24 rounded border border-softgraph bg-ink/40 px-3 py-2" data-testid="demoted-report-section">
            <summary className={`cursor-pointer select-none ${HEADING_CLASSES[section.heading.level] || 'text-sm font-semibold text-ivory'}`}>
              <InlineMarkdown text={section.heading.text} />
            </summary>
            <div className="mt-2 space-y-3">{section.entries.map(({ block, index }) => renderMarkdownBlock(block, index))}</div>
          </details>
        )
      })}
    </div>
  )
}

const OutlineList = ({ outline, onSelect, className = '' }) => (
  <ul className={`space-y-1 text-xs ${className}`}>
    {outline.map(entry => (
      <li key={entry.id} className={entry.level === 3 ? 'pl-3' : ''}>
        <button type="button" onClick={() => onSelect(entry.id)} className="text-left text-taupe transition-colors hover:text-champagne">
          {entry.text}
        </button>
      </li>
    ))}
  </ul>
)

// Renders one opened artifact/receipt tab's content. Handles the safe preview
// types the backend can actually serve: markdown, text/code/json, images, and
// PDFs (via a data-URI iframe, since the artifact route already returns base64
// for binary files — no new file-serving surface is introduced).
export default function ArtifactViewer({ tab, onCopyPath }) {
  const kind = artifactKind(tab?.extension)
  const blocks = useMemo(() => (tab && !tab.loading && !tab.error && kind === 'markdown') ? parseMarkdownBlocks(tab.content) : [], [tab, kind])
  const outline = useMemo(() => extractHeadingOutline(blocks), [blocks])
  // Same generic "repeated numbered entity" / no-external-action extraction
  // the Work Queue overview card uses, surfaced here too so the business
  // result (count, no-send state) is visible before any safety/verification
  // prose (F-REPORT-PRIORITY) — derived from content already loaded, no
  // second fetch.
  const highlights = useMemo(() => extractRepeatedEntitySummary(blocks), [blocks])
  const noExternalAction = useMemo(() => kind === 'markdown' && detectNoExternalAction(tab?.content), [tab?.content, kind])

  if (!tab) return null

  const scrollToHeading = id => {
    const target = document.getElementById(id)
    if (!target) return
    if (target.tagName === 'DETAILS') target.open = true
    else target.closest('details')?.setAttribute('open', '')
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-softgraph bg-graphite">
      <div className="flex flex-col gap-2 border-b border-softgraph px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ivory">{tab.label}</div>
          <div className="mt-0.5 break-all font-mono text-[11px] text-taupe">{tab.path}</div>
        </div>
        <button
          type="button"
          onClick={() => onCopyPath?.(tab.path)}
          className="inline-flex flex-shrink-0 items-center gap-2 self-start rounded border border-softgraph px-2 py-1.5 text-[11px] text-taupe transition-colors hover:border-champagne hover:text-stone sm:self-auto"
        >
          <Clipboard size={12} />
          Copy path
        </button>
      </div>
      {kind === 'markdown' && outline.length > 1 && !tab.loading && !tab.error && (
        <details className="border-b border-softgraph px-4 py-2 lg:hidden" data-testid="report-outline-mobile">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-taupe">Contents ({outline.length})</summary>
          <OutlineList outline={outline} onSelect={scrollToHeading} className="mt-2" />
        </details>
      )}
      <div className="flex flex-1 gap-4 p-4">
        {kind === 'markdown' && outline.length > 1 && !tab.loading && !tab.error && (
          // Sticky relative to the page's own scroll container (there is no
          // bounded-height ancestor here, so an overflow:auto wrapper around
          // this row would create a scroll context that never actually
          // scrolls — leaving `sticky` inert instead of pinned to the page).
          <nav
            className="sticky top-16 hidden max-h-[calc(100vh-5rem)] w-48 shrink-0 self-start overflow-y-auto lg:block"
            aria-label="Report outline"
            data-testid="report-outline-desktop"
          >
            <div className="text-[11px] font-semibold uppercase tracking-wider text-taupe">Contents</div>
            <OutlineList outline={outline} onSelect={scrollToHeading} className="mt-2" />
          </nav>
        )}
        <div className="min-w-0 flex-1" data-testid="artifact-markdown-body">
          {tab.loading ? (
            <div className="text-xs font-mono text-taupe">Loading {tab.label}…</div>
          ) : tab.error ? (
            <div className="text-xs font-mono text-clay">{tab.error}</div>
          ) : kind === 'image' ? (
            <div className="flex h-full items-center justify-center">
              <img src={`data:${tab.contentType || 'image/png'};base64,${tab.content}`} alt={tab.label} className="max-h-full max-w-full rounded border border-softgraph" />
            </div>
          ) : kind === 'pdf' ? (
            <iframe
              title={tab.label}
              src={`data:application/pdf;base64,${tab.content}`}
              className="h-full min-h-[70vh] w-full rounded border border-softgraph bg-ink"
            />
          ) : kind === 'markdown' ? (
            <div className="mx-auto w-full max-w-3xl">
              {(highlights || noExternalAction) && (
                <div className="mb-5 rounded border border-champagne/40 bg-champagne/5 px-3 py-2.5 text-sm text-stone" data-testid="report-result-highlight">
                  {highlights && (
                    <div>
                      <span className="font-semibold text-champagne">{highlights.count} selected</span>
                      {' — '}{highlights.names.join(' · ')}
                    </div>
                  )}
                  {noExternalAction && <div className={highlights ? 'mt-1 text-taupe' : 'text-taupe'}>No external action was taken.</div>}
                </div>
              )}
              <MarkdownPreview blocks={blocks} />
            </div>
          ) : (
            <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-stone">{tab.content || 'File is empty.'}</pre>
          )}
        </div>
      </div>
    </div>
  )
}
