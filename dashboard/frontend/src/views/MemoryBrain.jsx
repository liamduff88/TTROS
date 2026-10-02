// Revisit: when the Memory entity index or Business Brain reader contract changes. · Last touched: 2026-10-02.
import { useEffect, useMemo, useState } from 'react'
import { ChevronRight, Copy, Edit3, ExternalLink, FileText, Folder, FolderOpen, Save, Search, X } from 'lucide-react'
import { browseMemory, getMemoryDocument, getMemoryEntity, openMemoryPath, saveDashboardMemory, searchMemory } from '../api'
import { parseMarkdownBlocks } from '../artifactPreview'
import { MarkdownPreview } from '../components/ArtifactViewer'
import { ActionButton, EmptyState, PageHeader } from '../components/DashboardKit'
import { MemoryBoard } from './DashboardV1'

// Entity-first Business Brain browser. Every request here is a deterministic
// local read (search index + derived entity tables); nothing calls a model.

const FRONTMATTER_RE = /^---\s*\n[\s\S]*?\n---\s*\n/
const errorText = error => error?.response?.data?.detail || error?.message || 'Unavailable'
const ENTITY_TYPE_LABELS = { person: 'Person', prospect: 'Prospect', topic: 'Topic', company: 'Company', project: 'Project' }
const dateLabel = item => item.date_text || item.date || 'undated'

function Chip({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'border-softgraph text-taupe',
    canonical: 'border-champagne/60 text-champagne',
    evidence: 'border-clay/50 text-clay',
  }
  return <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] ${tones[tone]}`}>{children}</span>
}

function DocRow({ item, onOpen, showType = true }) {
  return (
    <button onClick={() => onOpen(item.path)} className="group flex w-full items-start justify-between gap-3 rounded border border-softgraph bg-graphite/50 px-3 py-2 text-left hover:border-champagne/40" data-testid="memory-doc-row">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-stone">{item.title}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-taupe">
          <span>{dateLabel(item)}</span>
          {showType && <span>· {item.type_label}</span>}
          {item.basis && <span className="opacity-70">· via {item.basis}</span>}
        </div>
      </div>
      <ChevronRight size={14} className="mt-1 shrink-0 text-taupe group-hover:text-champagne" />
    </button>
  )
}

function EntityCard({ entity, onSelect }) {
  return (
    <button onClick={() => onSelect(entity.entity_id)} className="group w-full rounded border border-softgraph bg-graphite/60 p-3 text-left hover:border-champagne/50" data-testid="memory-entity-result">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-ivory">{entity.display_name}</span>
        <Chip>{ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type}</Chip>
      </div>
      {entity.qualifier && <div className="mt-1 text-xs text-clay">{entity.qualifier}</div>}
      <div className="mt-1 text-xs text-taupe">{entity.knowledge_count} knowledge · {entity.source_count} sources{entity.latest_date ? ` · latest ${entity.latest_date}` : ''}</div>
    </button>
  )
}

function EntityView({ entityId, onOpenDoc, onSelectEntity }) {
  const [state, setState] = useState({ loading: true, data: null, error: '' })
  const [section, setSection] = useState('knowledge')
  const [oldestFirst, setOldestFirst] = useState(false)
  useEffect(() => {
    let alive = true
    setState({ loading: true, data: null, error: '' })
    setSection('knowledge')
    getMemoryEntity(entityId).then(data => alive && setState({ loading: false, data, error: '' })).catch(error => alive && setState({ loading: false, data: null, error: errorText(error) }))
    return () => { alive = false }
  }, [entityId])
  const groups = useMemo(() => {
    const result = new Map()
    for (const item of state.data?.knowledge || []) {
      if (!result.has(item.type_label)) result.set(item.type_label, [])
      result.get(item.type_label).push(item)
    }
    return [...result.entries()]
  }, [state.data])
  if (state.loading) return <EmptyState title="Loading entity" detail="Reading the local entity index." />
  if (state.error) return <EmptyState title="Entity unavailable" detail={state.error} />
  const { entity, knowledge, sources, timeline, related, similar_not_merged: similar, undated_count: undated } = state.data
  const importDated = state.data.import_dated || []
  const ordered = oldestFirst ? [...timeline].reverse() : timeline
  const sections = [
    ['knowledge', `Knowledge (${knowledge.length})`],
    ['sources', `Sources (${sources.length})`],
    ['timeline', `Timeline (${timeline.length})`],
    ['related', `Related (${related.length})`],
  ]
  return (
    <section className="rounded border border-softgraph bg-graphite/40 p-4" data-testid="memory-entity-view">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-xl font-semibold text-ivory" data-testid="memory-entity-name">{entity.display_name}</h2>
        <Chip>{ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type}</Chip>
        {entity.qualifier && <span className="text-xs text-clay">{entity.qualifier}</span>}
      </div>
      <div className="mt-1 text-xs text-taupe">{entity.knowledge_count} knowledge · {entity.source_count} sources{entity.latest_date ? ` · latest activity ${entity.latest_date}` : ''}</div>
      {entity.aliases?.length > 1 && <div className="mt-1 text-xs text-taupe">Also recorded as: {entity.aliases.filter(alias => alias !== entity.display_name).join(', ')}</div>}
      {similar.length > 0 && (
        <div className="mt-3 rounded border border-clay/40 bg-clay/5 p-3 text-xs text-stone" data-testid="memory-not-merged">
          <div className="mb-2">Similar name — <strong>not merged</strong>. No metadata declares these are the same person; open one to compare.</div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{similar.map(other => <EntityCard key={other.entity_id} entity={other} onSelect={onSelectEntity} />)}</div>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-1 border-b border-softgraph" role="tablist">
        {sections.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={section === id} onClick={() => setSection(id)} className={`px-3 py-1.5 text-xs font-semibold ${section === id ? 'border-b-2 border-champagne text-ivory' : 'text-taupe hover:text-stone'}`}>{label}</button>
        ))}
      </div>
      <div className="mt-3 space-y-4">
        {section === 'knowledge' && (groups.length ? groups.map(([label, items]) => (
          <div key={label}>
            <div className="mb-1.5 text-[11px] uppercase tracking-wider text-champagne">{label}</div>
            <div className="space-y-1.5">{items.map(item => <DocRow key={item.path} item={item} onOpen={onOpenDoc} showType={false} />)}</div>
          </div>
        )) : <EmptyState title="No linked knowledge" detail="No knowledge artifact declares this entity." />)}
        {section === 'sources' && (sources.length ? <div className="space-y-1.5">{sources.map(item => <DocRow key={item.path} item={item} onOpen={onOpenDoc} />)}</div> : <EmptyState title="No linked sources" detail="No original source declares this entity." />)}
        {section === 'timeline' && (
          <div data-testid="memory-timeline">
            <div className="mb-2 flex items-center justify-between text-xs text-taupe">
              <span>Dated by the event the record describes.</span>
              <button className="text-champagne hover:underline" onClick={() => setOldestFirst(value => !value)}>{oldestFirst ? 'Oldest first' : 'Newest first'} ⇅</button>
            </div>
            {ordered.length ? (
              <ol className="relative ml-2 space-y-2 border-l border-softgraph pl-4">
                {ordered.map(item => (
                  <li key={item.path} className="relative">
                    <span className={`absolute -left-[21px] top-3 h-2 w-2 rounded-full ${item.role === 'source' ? 'bg-clay' : 'bg-champagne'}`} />
                    <DocRow item={{ ...item, type_label: `${item.role === 'source' ? 'Source' : 'Knowledge'} · ${item.type_label}` }} onOpen={onOpenDoc} />
                  </li>
                ))}
              </ol>
            ) : <div className="text-xs text-taupe">No linked record carries an event date.</div>}
            {importDated.length > 0 && (
              <div className="mt-4" data-testid="memory-import-dated">
                <div className="mb-1.5 text-[11px] uppercase tracking-wider text-champagne">Event date not recorded · import date only</div>
                <div className="space-y-1.5">{importDated.map(item => <DocRow key={item.path} item={{ ...item, type_label: `${item.role === 'source' ? 'Source' : 'Knowledge'} · ${item.type_label}` }} onOpen={onOpenDoc} />)}</div>
              </div>
            )}
            {undated > 0 && <div className="mt-3 text-xs text-taupe">{undated} linked item{undated === 1 ? '' : 's'} without any recorded date (see Knowledge / Sources).</div>}
          </div>
        )}
        {section === 'related' && (related.length ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {related.map(other => (
              <button key={other.entity_id} onClick={() => onSelectEntity(other.entity_id)} className="rounded border border-softgraph bg-graphite/50 px-3 py-2 text-left hover:border-champagne/40">
                <div className="text-sm font-semibold text-stone">{other.display_name}</div>
                <div className="text-xs text-taupe">{ENTITY_TYPE_LABELS[other.entity_type] || other.entity_type} · {other.shared} shared record{other.shared === 1 ? '' : 's'}</div>
              </button>
            ))}
          </div>
        ) : <EmptyState title="No related entities" detail="No other entity is declared on the same records." />)}
      </div>
    </section>
  )
}

function DocumentReader({ path, onClose, onOpenDoc, onSelectEntity }) {
  const [doc, setDoc] = useState({ loading: true, data: null, error: '' })
  const [raw, setRaw] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [notice, setNotice] = useState({ tone: '', text: '' })
  const load = () => {
    setDoc({ loading: true, data: null, error: '' })
    return getMemoryDocument(path).then(data => setDoc({ loading: false, data, error: '' })).catch(error => setDoc({ loading: false, data: null, error: errorText(error) }))
  }
  useEffect(() => { setRaw(false); setEditing(false); setNotice({ tone: '', text: '' }); load() }, [path])
  const data = doc.data
  const body = useMemo(() => (data?.content || '').replace(FRONTMATTER_RE, ''), [data])
  const frontmatter = useMemo(() => (data?.content || '').match(FRONTMATTER_RE)?.[0] || '', [data])
  const blocks = useMemo(() => parseMarkdownBlocks(body), [body])
  const act = async (label, fn) => {
    try {
      await fn()
      setNotice({ tone: 'ok', text: label })
    } catch (error) {
      setNotice({ tone: 'error', text: errorText(error) })
    }
  }
  const save = () => act('Saved. Search index refreshed.', async () => {
    await saveDashboardMemory({ path, content: draft, expected_revision: data.revision })
    setEditing(false)
    await load()
  })
  const meta = data?.meta || {}
  return (
    <div className="fixed inset-y-0 right-0 z-30 flex w-full max-w-3xl flex-col border-l border-softgraph bg-graphite shadow-2xl" data-testid="memory-reader">
      <div className="flex items-start justify-between gap-3 border-b border-softgraph p-4">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-1.5">
            {meta.type_label && <Chip>{meta.role === 'source' ? 'Source' : 'Knowledge'} · {meta.type_label}</Chip>}
            {data && <Chip tone={meta.canonical ? 'canonical' : 'evidence'}>{meta.canonical ? 'Canonical Business Brain' : 'Evidence · not canonical'}</Chip>}
            {meta.date_text && <Chip>{meta.date_text}</Chip>}
          </div>
          <h2 className="mt-2 text-lg font-semibold text-ivory" data-testid="memory-reader-title">{data?.title || 'Loading…'}</h2>
        </div>
        <button onClick={onClose} className="rounded p-1 text-taupe hover:bg-softgraph hover:text-stone" aria-label="Close document"><X size={18} /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {doc.loading && <EmptyState title="Loading full document" detail="Reading the Business Brain file." />}
        {doc.error && <EmptyState title="Unable to open document" detail={doc.error} />}
        {data && <>
          <div className="mb-3 flex flex-wrap gap-2">
            <ActionButton onClick={() => act('Opened in Windows.', () => openMemoryPath(path, 'file'))} disabled={!data.windows_path}><ExternalLink size={13} />Open in Windows</ActionButton>
            <ActionButton onClick={() => act('Opened containing folder.', () => openMemoryPath(path, 'folder'))} disabled={!data.windows_path}><FolderOpen size={13} />Open containing folder</ActionButton>
            <ActionButton onClick={() => act('Windows path copied.', () => navigator.clipboard.writeText(data.windows_path))} disabled={!data.windows_path}><Copy size={13} />Copy Windows path</ActionButton>
            {data.editable && !editing && <ActionButton onClick={() => { setDraft(data.content); setEditing(true) }}><Edit3 size={13} />Edit</ActionButton>}
            {editing && <ActionButton kind="primary" onClick={save}><Save size={13} />Save</ActionButton>}
            {editing && <ActionButton onClick={() => setEditing(false)}><X size={13} />Cancel</ActionButton>}
            {!editing && <ActionButton onClick={() => setRaw(value => !value)}><FileText size={13} />{raw ? 'Formatted' : 'Raw file'}</ActionButton>}
          </div>
          <div className="mb-3 break-all font-mono text-[11px] text-taupe" data-testid="memory-windows-path">{data.windows_path}</div>
          {!data.editable && data.edit_block_reason && <div className="mb-3 text-xs text-taupe" data-testid="memory-read-only">{data.edit_block_reason}</div>}
          {notice.text && <div role={notice.tone === 'error' ? 'alert' : 'status'} className={`mb-3 rounded border px-3 py-2 text-xs ${notice.tone === 'error' ? 'border-clay/70 text-clay' : 'border-champagne/50 text-champagne'}`}>{notice.text}</div>}
          {meta.entities?.length > 0 && (
            <div className="mb-4 flex flex-wrap items-center gap-1.5 text-xs text-taupe">
              Linked:
              {meta.entities.map(entity => <button key={entity.entity_id} onClick={() => onSelectEntity(entity.entity_id)} title={`via ${entity.basis}`} className="rounded border border-softgraph px-1.5 py-0.5 text-stone hover:border-champagne/50">{entity.display_name}</button>)}
            </div>
          )}
          {editing ? (
            <textarea aria-label={`Markdown content for ${path}`} value={draft} onChange={event => setDraft(event.target.value)} className="min-h-[60vh] w-full rounded border border-softgraph bg-ink px-3 py-2 font-mono text-xs leading-5 text-stone" />
          ) : raw ? (
            <pre className="whitespace-pre-wrap rounded border border-softgraph bg-ink p-3 text-xs leading-5 text-stone" data-testid="memory-raw-content">{data.content}</pre>
          ) : (
            <div data-testid="memory-document-body"><MarkdownPreview blocks={blocks} /></div>
          )}
          <div className="mt-6 rounded border border-softgraph bg-ink/40 p-3 text-xs text-taupe" data-testid="memory-graphify">
            <div className="mb-1 font-semibold uppercase tracking-wider text-champagne">Graphify · derived links</div>
            {!data.graphify?.available ? data.graphify?.reason : !data.graphify.in_graph ? `Not in the published Business Brain Graphify projection (built ${data.graphify.graph_built}).` : (
              data.graphify.links.length ? <div className="space-y-1">{data.graphify.links.map(link => <button key={link.path} className="block text-left text-stone hover:text-champagne" onClick={() => onOpenDoc(link.path)}>↔ {link.title}</button>)}</div> : 'In the projection with no wiki-linked notes.'
            )}
          </div>
          <details className="mt-3 text-xs text-taupe">
            <summary className="cursor-pointer">Technical details</summary>
            <div className="mt-2 space-y-1 break-all font-mono">
              <div>pointer: {data.path}</div>
              <div>wsl: {data.wsl_path}</div>
              {meta.package_id && <div>ingest package: {meta.package_id}</div>}
              {meta.date_basis && <div>date basis: {meta.date_basis}</div>}
              {data.graphify?.node_id && <div>graphify node: {data.graphify.node_id}</div>}
              {meta.entities?.map(entity => <div key={entity.entity_id}>{entity.entity_id} ← {entity.basis}</div>)}
              {frontmatter && <pre className="mt-2 whitespace-pre-wrap rounded border border-softgraph bg-ink p-2">{frontmatter}</pre>}
            </div>
          </details>
        </>}
      </div>
    </div>
  )
}

function FilesView({ onOpenDoc, initialDir = '' }) {
  const [dir, setDir] = useState(initialDir)
  const [state, setState] = useState({ loading: true, data: null, error: '' })
  const [notice, setNotice] = useState('')
  useEffect(() => {
    let alive = true
    setState(current => ({ ...current, loading: true, error: '' }))
    browseMemory(dir).then(data => alive && setState({ loading: false, data, error: '' })).catch(error => alive && setState({ loading: false, data: null, error: errorText(error) }))
    return () => { alive = false }
  }, [dir])
  const crumbs = dir ? dir.split('/') : []
  return (
    <section data-testid="memory-files-view">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1 text-sm">
          <button className="text-champagne hover:underline" onClick={() => setDir('')}>Business Brain</button>
          {crumbs.map((part, index) => <span key={index} className="flex items-center gap-1 text-taupe"><ChevronRight size={12} /><button className="text-champagne hover:underline" onClick={() => setDir(crumbs.slice(0, index + 1).join('/'))}>{part}</button></span>)}
        </div>
        <ActionButton onClick={() => openMemoryPath(dir, 'dir').then(() => setNotice('Folder opened in Windows.')).catch(error => setNotice(errorText(error)))}><FolderOpen size={13} />Open folder in Windows</ActionButton>
      </div>
      {notice && <div role="status" className="mb-2 text-xs text-champagne">{notice}</div>}
      {state.error && <EmptyState title="Folder unavailable" detail={state.error} />}
      {state.data && (
        <div className="space-y-1">
          {state.data.folders.map(folder => (
            <button key={folder.dir} onClick={() => setDir(folder.dir)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-stone hover:bg-softgraph/40"><Folder size={14} className="text-champagne" />{folder.name}</button>
          ))}
          {state.data.files.map(file => (
            <button key={file.path} disabled={!file.readable} onClick={() => onOpenDoc(file.path)} title={file.readable ? file.path : 'Outside the global Memory scope'} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-stone hover:bg-softgraph/40 disabled:cursor-not-allowed disabled:opacity-40">
              <FileText size={14} className="text-taupe" />{file.name}{!file.readable && <span className="text-xs text-taupe">· not in Memory scope</span>}
            </button>
          ))}
          {!state.data.folders.length && !state.data.files.length && <div className="text-sm text-taupe">Empty folder.</div>}
        </div>
      )}
    </section>
  )
}

const MODES = [['entities', 'Entities'], ['files', 'Browse files'], ['canonical', 'Canonical notes']]

export default function MemoryBrain({ initialFilters = {} }) {
  const [mode, setMode] = useState(MODES.some(([id]) => id === initialFilters.memoryMode) ? initialFilters.memoryMode : 'entities')
  const [query, setQuery] = useState(initialFilters.q || '')
  const [entityId, setEntityId] = useState(initialFilters.entity || '')
  const [results, setResults] = useState({ loading: false, data: null, error: '' })
  const [readerPath, setReaderPath] = useState('')

  const selectEntity = id => { setEntityId(id); setMode('entities') }

  useEffect(() => {
    const q = query.trim()
    if (!q) { setResults({ loading: false, data: null, error: '' }); return undefined }
    let alive = true
    setResults(current => ({ ...current, loading: true, error: '' }))
    const timer = window.setTimeout(() => {
      searchMemory(q).then(data => {
        if (!alive) return
        setResults({ loading: false, data, error: '' })
        const only = data.entities?.[0]
        if (data.resolution === 'single' && only?.match === 'exact') selectEntity(only.entity_id)
      }).catch(error => alive && setResults({ loading: false, data: null, error: errorText(error) }))
    }, 200)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [query])

  const onQuery = value => {
    setQuery(value)
    setEntityId('')
  }
  const data = results.data
  return (
    <>
      <PageHeader title="Memory" question="Search an entity to see what TTROS knows — knowledge, original sources, timeline and related entities. Local index only; no model calls." actions={
        <div className="flex gap-1 rounded border border-softgraph p-0.5" role="tablist" aria-label="Memory mode">
          {MODES.map(([id, label]) => (
            <button key={id} role="tab" aria-selected={mode === id} onClick={() => setMode(id)} className={`rounded px-3 py-1 text-xs font-semibold ${mode === id ? 'bg-softgraph text-ivory' : 'text-taupe hover:text-stone'}`}>{label}</button>
          ))}
        </div>
      } />
      {mode === 'entities' ? <>
        <label className="mb-4 flex items-center gap-2 rounded border border-softgraph bg-ink px-3 py-2 focus-within:border-champagne/60">
          <Search size={15} className="text-taupe" />
          <input autoFocus value={query} onChange={event => onQuery(event.target.value)} placeholder="Search people, companies, projects, topics or files…" aria-label="Search memory" data-testid="memory-search-input" className="w-full bg-transparent text-sm text-stone outline-none placeholder:text-taupe" />
          {query && <button onClick={() => onQuery('')} aria-label="Clear search" className="text-taupe hover:text-stone"><X size={14} /></button>}
        </label>
        {entityId ? (
          <>
            {data?.entities?.length > 1 && <button onClick={() => setEntityId('')} className="mb-2 text-xs text-champagne hover:underline">← {data.entities.length} matches for “{query}”</button>}
            <EntityView entityId={entityId} onOpenDoc={setReaderPath} onSelectEntity={selectEntity} />
          </>
        ) : !query.trim() ? (
          <EmptyState title="Start with a name" detail="Type a person, company, prospect or topic. Matching entities appear first; knowledge and source files follow." />
        ) : (
          <div className="space-y-5" data-testid="memory-search-results">
            {results.error && <EmptyState title="Search unavailable" detail={results.error} />}
            {data?.entities?.length > 0 && (
              <div>
                <div className="mb-2 text-[11px] uppercase tracking-wider text-champagne">{data.resolution === 'ambiguous' ? `Entities · ${data.entities.length} matches — choose one` : 'Entity'}</div>
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{data.entities.map(entity => <EntityCard key={entity.entity_id} entity={entity} onSelect={selectEntity} />)}</div>
              </div>
            )}
            {data?.knowledge?.length > 0 && <div><div className="mb-2 text-[11px] uppercase tracking-wider text-champagne">Knowledge</div><div className="space-y-1.5">{data.knowledge.map(item => <DocRow key={item.path} item={item} onOpen={setReaderPath} />)}</div></div>}
            {data?.sources?.length > 0 && <div><div className="mb-2 text-[11px] uppercase tracking-wider text-champagne">Sources</div><div className="space-y-1.5">{data.sources.map(item => <DocRow key={item.path} item={item} onOpen={setReaderPath} />)}</div></div>}
            {data && !data.entities.length && !data.knowledge.length && !data.sources.length && <EmptyState title="No matches" detail="Nothing in the local Business Brain index matched." />}
            {data && <div className="text-[11px] text-taupe">{data.latency_ms} ms · {data.token_usage_text}</div>}
          </div>
        )}
      </> : mode === 'files' ? <FilesView onOpenDoc={setReaderPath} /> : <MemoryBoard />}
      {readerPath && <DocumentReader path={readerPath} onClose={() => setReaderPath('')} onOpenDoc={setReaderPath} onSelectEntity={id => { setReaderPath(''); selectEntity(id) }} />}
    </>
  )
}
