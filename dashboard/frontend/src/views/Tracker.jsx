import { useState, useEffect } from 'react'
import { DollarSign, Clock, TrendingUp, Save, Check } from 'lucide-react'
import { getTracker, updateTracker } from '../api'

const StatCard = ({ label, value, sub, icon: Icon, accent }) => (
  <div className="bg-graphite border border-softgraph rounded-lg p-5">
    <div className="flex items-center justify-between mb-3">
      <span className="text-xs text-taupe font-medium uppercase tracking-wider">{label}</span>
      <Icon size={14} className={accent || 'text-taupe'} />
    </div>
    <div className={`text-3xl font-mono font-semibold ${accent || 'text-ivory'}`}>{value}</div>
    {sub && <div className="text-xs text-taupe mt-1.5">{sub}</div>}
  </div>
)

export default function Tracker() {
  const [data, setData] = useState({ hourlyRate: 150, estimatedHoursSaved: 0, estimatedValue: 0 })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getTracker().then(setData).catch(() => {})
  }, [])

  const set = (k, v) => setData(d => {
    const next = { ...d, [k]: parseFloat(v) || 0 }
    next.estimatedValue = Math.round(next.hourlyRate * next.estimatedHoursSaved * 100) / 100
    return next
  })

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateTracker({ hourlyRate: data.hourlyRate, estimatedHoursSaved: data.estimatedHoursSaved })
      setData(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {}
    finally { setSaving(false) }
  }

  const valueColor = data.estimatedValue > 1000 ? 'text-champagne' : data.estimatedValue > 0 ? 'text-stone' : 'text-taupe'

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ivory mb-1">Time & Value Tracker</h1>
        <p className="text-sm text-taupe">Local-only calculation. Zero API calls. State saved to /dashboard/data/tracker.json.</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="Hourly Rate"
          value={`$${data.hourlyRate}`}
          sub="per hour (your estimate)"
          icon={DollarSign}
          accent="text-stone"
        />
        <StatCard
          label="Hours Saved"
          value={data.estimatedHoursSaved.toFixed(1)}
          sub="estimated by AI assistance"
          icon={Clock}
          accent="text-stone"
        />
        <StatCard
          label="Estimated Value"
          value={`$${data.estimatedValue.toLocaleString()}`}
          sub="hourly rate × hours saved"
          icon={TrendingUp}
          accent={valueColor}
        />
      </div>

      <div className="bg-graphite border border-softgraph rounded-lg p-6">
        <h2 className="text-xs font-semibold text-taupe uppercase tracking-wider mb-5">Adjust Inputs</h2>

        <div className="space-y-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-stone font-medium">Hourly Rate</label>
              <span className="text-lg font-mono font-semibold text-ivory">${data.hourlyRate}/hr</span>
            </div>
            <input
              type="range"
              min={25}
              max={500}
              step={5}
              value={data.hourlyRate}
              onChange={e => set('hourlyRate', e.target.value)}
              className="w-full h-1.5 bg-softgraph rounded appearance-none cursor-pointer accent-champagne"
            />
            <div className="flex justify-between text-[10px] text-taupe font-mono mt-1">
              <span>$25</span>
              <span>$500</span>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-stone font-medium">Estimated Hours Saved</label>
              <span className="text-lg font-mono font-semibold text-ivory">{data.estimatedHoursSaved.toFixed(1)} hrs</span>
            </div>
            <input
              type="range"
              min={0}
              max={200}
              step={0.5}
              value={data.estimatedHoursSaved}
              onChange={e => set('estimatedHoursSaved', e.target.value)}
              className="w-full h-1.5 bg-softgraph rounded appearance-none cursor-pointer accent-champagne"
            />
            <div className="flex justify-between text-[10px] text-taupe font-mono mt-1">
              <span>0 hrs</span>
              <span>200 hrs</span>
            </div>
          </div>

          <div className="pt-2 border-t border-softgraph">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-taupe font-mono mb-1">Estimated Value</div>
                <div className={`text-2xl font-mono font-bold ${valueColor}`}>
                  ${data.estimatedValue.toLocaleString()}
                </div>
              </div>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 rounded bg-champagne text-ivory text-sm font-semibold hover:bg-well disabled:opacity-40 transition-colors"
              >
                {saved ? <Check size={13} /> : <Save size={13} />}
                {saving ? 'Saving…' : saved ? 'Saved' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-graphite border border-softgraph rounded-lg p-5">
        <h2 className="text-xs font-semibold text-taupe uppercase tracking-wider mb-3">How to Use</h2>
        <ul className="space-y-1.5 text-xs text-taupe">
          <li className="flex gap-2"><span className="text-champagne">1.</span> Set your effective hourly rate (billing rate or opportunity cost)</li>
          <li className="flex gap-2"><span className="text-champagne">2.</span> Estimate hours saved by AI assistance across your work session</li>
          <li className="flex gap-2"><span className="text-champagne">3.</span> Hit Save — state persists locally at /dashboard/data/tracker.json</li>
          <li className="flex gap-2"><span className="text-champagne">4.</span> Value appears in the Overview metric strip and Top Bar</li>
        </ul>
      </div>
    </div>
  )
}
