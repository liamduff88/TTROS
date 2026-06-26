import { useState } from 'react'
import { FileText, Save, Check, AlertCircle, Copy } from 'lucide-react'
import { createPacket } from '../api'

const TARGETS = ['Claude Code', 'Codex', 'Antigravity', 'ChatGPT', 'Hermes', 'Human Review']
const PRESETS = [
  { id: 'code', label: 'Code Task' },
  { id: 'analysis', label: 'Analysis' },
  { id: 'writing', label: 'Writing' },
  { id: 'research', label: 'Research' },
  { id: 'review', label: 'Review' },
  { id: 'strategy', label: 'Strategy' },
]

export default function PacketCreator({ onRefresh }) {
  const [form, setForm] = useState({ target: TARGETS[0], preset: PRESETS[0].id, task: '' })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(null)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const preview = `TARGET: ${form.target}
PRESET: ${form.preset.toUpperCase()}
CREATED: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC
STATUS: pending

---

${form.task || '[Task text will appear here]'}`

  const handleSave = async () => {
    if (!form.task.trim()) { setError('Task text is required'); return }
    setSaving(true)
    setError(null)
    try {
      const result = await createPacket(form)
      setSaved(result)
      setForm(f => ({ ...f, task: '' }))
      if (onRefresh) onRefresh()
      setTimeout(() => setSaved(null), 5000)
    } catch {
      setError('Failed to save packet — is the backend running on :8010?')
    } finally {
      setSaving(false)
    }
  }

  const handleCopyPreview = () => {
    navigator.clipboard.writeText(preview).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ivory mb-1">Packet Creator</h1>
        <p className="text-sm text-taupe">Create task packets for agents. Saved locally to /packets/ — not auto-sent.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-5">
          <div className="bg-graphite border border-softgraph rounded-lg p-5 space-y-4">
            <h2 className="text-xs font-semibold text-taupe uppercase tracking-wider">Configure Packet</h2>

            <div>
              <label className="block text-xs text-taupe mb-2 font-medium">Target Agent</label>
              <select
                value={form.target}
                onChange={e => set('target', e.target.value)}
                className="w-full bg-ink border border-softgraph rounded px-3 py-2 text-sm text-ivory font-mono focus:outline-none focus:border-taupe"
              >
                {TARGETS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs text-taupe mb-2 font-medium">Task Preset</label>
              <div className="grid grid-cols-3 gap-2">
                {PRESETS.map(p => (
                  <button
                    key={p.id}
                    onClick={() => set('preset', p.id)}
                    className={`px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
                      form.preset === p.id
                        ? 'bg-champagne text-ink'
                        : 'bg-softgraph text-taupe hover:text-stone'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs text-taupe mb-2 font-medium">Task</label>
              <textarea
                value={form.task}
                onChange={e => set('task', e.target.value)}
                placeholder="Describe the task clearly. Be specific about inputs, expected outputs, and constraints."
                rows={8}
                className="w-full bg-ink border border-softgraph rounded px-3 py-2.5 text-sm text-ivory placeholder-taupe/50 font-sans resize-none focus:outline-none focus:border-taupe"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-clay/10 border border-clay/30 text-xs text-stone font-mono">
                <AlertCircle size={11} className="text-clay flex-shrink-0" />
                {error}
              </div>
            )}

            {saved && (
              <div className="flex items-center gap-2 px-3 py-2 rounded bg-olive/10 border border-olive/30 text-xs text-stone font-mono">
                <Check size={11} className="text-olive flex-shrink-0" />
                Saved: {saved.filename}
              </div>
            )}

            <button
              onClick={handleSave}
              disabled={saving || !form.task.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded bg-champagne text-ink text-sm font-semibold hover:bg-stone disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <Save size={13} />
              {saving ? 'Saving…' : 'Save Packet'}
            </button>
          </div>
        </div>

        <div className="bg-graphite border border-softgraph rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-taupe uppercase tracking-wider">Preview</h2>
            <button
              onClick={handleCopyPreview}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono bg-softgraph text-taupe hover:text-stone transition-colors"
            >
              {copied ? <Check size={10} className="text-olive" /> : <Copy size={10} />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="text-xs font-mono text-stone leading-relaxed whitespace-pre-wrap bg-ink rounded p-4 border border-softgraph min-h-48">
            {preview}
          </pre>
          <p className="text-[10px] text-taupe font-mono mt-3">
            Packets are saved to: Agentic OS Live/packets/packet_YYYYMMDD_HHMMSS.json
          </p>
        </div>
      </div>
    </div>
  )
}
