import { useRef, useState } from 'react'
import { Inbox } from 'lucide-react'
import { createInboxCapture } from '../api'

const newCaptureId = () => globalThis.crypto?.randomUUID?.() || `dashboard-${Date.now()}-${Math.random().toString(16).slice(2)}`

export default function CaptureBox() {
  const [text, setText] = useState('')
  const [focused, setFocused] = useState(false)
  const [state, setState] = useState({ status: 'idle', message: '' })
  const captureId = useRef(newCaptureId())

  const submit = async event => {
    event?.preventDefault()
    if (!text.trim() || state.status === 'saving') return
    setState({ status: 'saving', message: 'Capturing…' })
    try {
      const result = await createInboxCapture(text, captureId.current)
      setText('')
      captureId.current = newCaptureId()
      setState({ status: 'saved', message: result.duplicate ? 'Already captured' : 'Captured to Business Brain inbox' })
    } catch (error) {
      setState({ status: 'error', message: error?.response?.data?.detail || error?.message || 'Capture failed' })
    }
  }

  const onKeyDown = event => {
    if (event.key === 'Enter' && event.ctrlKey) submit(event)
  }

  return (
    <form onSubmit={submit} className="shrink-0 border-b border-softgraph bg-graphite px-3 py-2" data-testid="cockpit-capture-box">
      <div className="flex items-end gap-2">
        <Inbox size={15} className="mb-2 text-champagne" aria-hidden="true" />
        <textarea
          value={text}
          rows={focused || text.includes('\n') ? 3 : 1}
          onChange={event => setText(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
          placeholder="Capture a note… Ctrl+Enter"
          aria-label="Capture a note to the Business Brain inbox"
          className="min-h-8 max-h-32 flex-1 resize-none rounded border border-softgraph bg-ink px-3 py-1.5 text-sm text-stone outline-none placeholder:text-taupe focus:border-champagne/60"
        />
        <button type="submit" disabled={!text.trim() || state.status === 'saving'} className="h-8 rounded border border-champagne/80 bg-champagne px-3 text-xs font-semibold text-ivory disabled:cursor-not-allowed disabled:opacity-50">
          {state.status === 'saving' ? 'Capturing' : 'Capture'}
        </button>
      </div>
      {state.message && <div role="status" className={`ml-6 mt-1 text-xs ${state.status === 'error' ? 'text-clay' : 'text-taupe'}`}>{state.message}</div>}
    </form>
  )
}
