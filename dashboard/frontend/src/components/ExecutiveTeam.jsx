// Revisit: when the Cockpit Executive Team consultation contract changes. · Last touched: 2026-08-01.

import { useEffect, useReducer, useRef, useState } from 'react'
import { RefreshCw, Send, ShieldCheck, Users } from 'lucide-react'
import { consultExecutive } from '../api'
import {
  EXECUTIVE_TEAM_MEMBERS,
  canSubmitExecutiveConsultation,
  executiveApiError,
  executiveConsultationReducer,
  initialExecutiveConsultation,
} from '../executiveTeamState'
import { ActionButton, StatusChip } from './DashboardKit'

const newRequestId = () => globalThis.crypto?.randomUUID?.() || `exec-${Date.now()}-${Math.random().toString(16).slice(2)}`

function EvidenceGrid({ result }) {
  if (!result) return null
  const context = result.context || {}
  return (
    <div className="mt-3 rounded border border-softgraph bg-ink p-3" data-testid="executive-evidence">
      <div className="grid gap-2 text-xs text-taupe md:grid-cols-2 xl:grid-cols-3">
        <div><span className="text-stone">Requested profile:</span> <span className="font-mono">{result.requested_profile || 'unavailable'}</span></div>
        <div><span className="text-stone">Actual profile:</span> <span className="font-mono">{result.actual_profile || 'not started'}</span></div>
        <div><span className="text-stone">Fallback:</span> <span className={result.fallback_occurred ? 'text-clay' : 'text-olive'}>{result.fallback_occurred ? 'occurred — blocked' : 'none'}</span></div>
        <div><span className="text-stone">Context:</span> {context.classification || 'unavailable'}</div>
        <div><span className="text-stone">Queue effect:</span> {result.queue_effect?.unchanged === false ? 'change detected' : `${result.queue_effect?.items_created || 0} items created`}</div>
        <div><span className="text-stone">Request:</span> <span className="font-mono">{result.request_id || 'unavailable'}</span>{result.idempotency?.replayed ? ' · replayed' : ''}</div>
      </div>
      <div className="mt-2 space-y-1 border-t border-softgraph pt-2 text-[11px] text-taupe">
        {(context.sources || []).map((source, index) => (
          <div key={`${source.label}-${index}`}>
            <span className="text-stone">{source.label}:</span> {source.path || source.profile || 'unavailable'}
            {typeof source.byte_count === 'number' ? ` · ${source.byte_count} bytes` : ''}
            {source.sha256 ? ` · sha256 ${source.sha256.slice(0, 16)}…` : ''}
            {source.available === false ? ' · unavailable' : ''}
          </div>
        ))}
        <div>Executive Header included: {context.executive_header_included ? 'yes' : 'no'} · Full Executive Brief included: {context.executive_brief_included ? 'yes' : 'no'}</div>
      </div>
    </div>
  )
}

export default function ExecutiveTeam() {
  const [selectedId, setSelectedId] = useState('')
  const [request, setRequest] = useState('')
  const [state, dispatch] = useReducer(executiveConsultationReducer, initialExecutiveConsultation)
  const textareaRef = useRef(null)
  const submissionRef = useRef(null)
  const requestIdRef = useRef('')
  const selected = EXECUTIVE_TEAM_MEMBERS.find(member => member.id === selectedId)

  useEffect(() => {
    if (selected) textareaRef.current?.focus()
  }, [selectedId])

  const selectExecutive = member => {
    setSelectedId(member.id)
    setRequest('')
    requestIdRef.current = ''
    submissionRef.current = null
    dispatch({ type: 'reset' })
  }

  const changeRequest = event => {
    setRequest(event.target.value)
    requestIdRef.current = ''
    if (state.status !== 'idle') dispatch({ type: 'reset' })
  }

  const submit = async event => {
    event?.preventDefault?.()
    const text = request.trim()
    if (!selected || !canSubmitExecutiveConsultation(state, text) || submissionRef.current) return submissionRef.current
    const requestId = requestIdRef.current || newRequestId()
    requestIdRef.current = requestId
    dispatch({ type: 'start' })
    const pending = consultExecutive({ executive_id: selected.id, text, request_id: requestId })
      .then(result => {
        if (result?.success) dispatch({ type: 'success', result })
        else dispatch({ type: 'failure', result, error: result?.error?.message || 'The named profile failed.' })
        return result
      })
      .catch(error => {
        dispatch({ type: 'failure', error: executiveApiError(error) })
        return null
      })
      .finally(() => { submissionRef.current = null })
    submissionRef.current = pending
    return pending
  }

  return (
    <section className="mb-4 rounded border border-champagne/40 bg-graphite p-4" data-testid="executive-team">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-champagne"><Users size={14} />SPECIALIST PERSPECTIVES</div>
          <h2 className="mt-1 text-lg font-semibold text-ivory">Pick a department view</h2>
          <p className="mt-1 text-xs text-taupe">Optional. Use this only when you deliberately want one department's judgment instead of David's. Consultations do not create queue work or take external action.</p>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-olive"><ShieldCheck size={13} /> Named profiles · no silent fallback</div>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3" data-testid="executive-cards">
        {EXECUTIVE_TEAM_MEMBERS.map(member => {
          const active = member.id === selectedId
          return (
            <button
              key={member.id}
              type="button"
              onClick={() => selectExecutive(member)}
              aria-pressed={active}
              data-executive-card={member.id}
              data-profile={member.profile}
              className={`rounded border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-champagne/50 ${active ? 'border-champagne bg-champagne/10' : 'border-softgraph bg-ink hover:border-champagne/50'}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-semibold text-stone">{member.name}</span>
                {active && <StatusChip status="Running">Selected</StatusChip>}
              </div>
              <div className="mt-1 font-mono text-[11px] text-champagne">{member.profile}</div>
              <div className="mt-2 text-xs text-taupe">{member.remit}</div>
            </button>
          )
        })}
      </div>

      {selected && (
        <form onSubmit={submit} className="mt-3 rounded border border-softgraph bg-graphite/70 p-3" data-testid="executive-composer">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor="executive-request" className="text-xs font-semibold text-stone">Consulting {selected.name}</label>
            <span className="font-mono text-[11px] text-champagne">Requested profile: {selected.profile}</span>
          </div>
          <textarea
            ref={textareaRef}
            id="executive-request"
            value={request}
            onChange={changeRequest}
            maxLength={8000}
            placeholder={`Ask ${selected.name} for judgment…`}
            className="mt-2 min-h-20 w-full resize-y rounded border border-softgraph bg-ink px-3 py-2 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne/60"
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <ActionButton kind="primary" type="submit" disabled={!canSubmitExecutiveConsultation(state, request)}>
              <Send size={13} />{state.status === 'loading' ? 'Consulting…' : `Ask ${selected.name}`}
            </ActionButton>
            {state.status === 'failure' && requestIdRef.current && (
              <ActionButton onClick={submit}><RefreshCw size={13} />Retry safely</ActionButton>
            )}
            {state.status === 'loading' && <span className="text-xs text-champagne" role="status">The named profile is responding…</span>}
          </div>

          {state.status === 'success' && (
            <div className="mt-3 rounded border border-olive/50 bg-olive/10 p-3" data-testid="executive-success">
              <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-olive">Consultation complete</span><StatusChip status="Done" /></div>
              <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap font-sans text-sm leading-6 text-stone">{state.result.response}</pre>
            </div>
          )}
          {state.status === 'failure' && (
            <div className="mt-3 rounded border border-clay/70 bg-clay/10 p-3" data-testid="executive-failure" role="alert">
              <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-clay">Consultation failed</span><StatusChip status="Blocked" /></div>
              <p className="mt-2 text-sm text-stone">{state.error}</p>
              <p className="mt-1 text-xs text-taupe">No successful response is being shown. Check the named profile, backend route, authentication, context freshness, or timeout detail above.</p>
            </div>
          )}
          <EvidenceGrid result={state.result} />
        </form>
      )}
    </section>
  )
}
