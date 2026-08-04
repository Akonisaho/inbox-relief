import { useEffect, useState } from 'react'
import { api, type Rule } from '../api'
import { UrgencyBadge } from './Badge'

export function RulesPanel() {
  const [rules, setRules] = useState<Rule[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [matchField, setMatchField] = useState<'sender' | 'subject'>('sender')
  const [matchValue, setMatchValue] = useState('')
  const [shouldArchive, setShouldArchive] = useState(true)
  const [urgency, setUrgency] = useState('low')

  const load = () => {
    api
      .rules()
      .then(setRules)
      .catch((e) => setError(String(e)))
  }

  useEffect(load, [])

  const handleCreate = async () => {
    if (!matchValue.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.createRule({ match_field: matchField, match_value: matchValue.trim(), should_archive: shouldArchive, urgency })
      setMatchValue('')
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.deleteRule(id)
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Rules</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Standing policies that skip classification entirely when matched — either create one
        below, or say something like "always archive emails from noreply@x.com" in Chat.
      </p>

      <div className="mb-8 rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-soft">
              When
            </label>
            <select
              value={matchField}
              onChange={(e) => setMatchField(e.target.value as 'sender' | 'subject')}
              className="w-full rounded-md border border-border bg-paper px-2 py-1.5 text-sm"
            >
              <option value="sender">Sender contains</option>
              <option value="subject">Subject contains</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-soft">
              Value
            </label>
            <input
              value={matchValue}
              onChange={(e) => setMatchValue(e.target.value)}
              placeholder="e.g. noreply@x.com"
              className="w-full rounded-md border border-border bg-paper px-2 py-1.5 text-sm outline-none focus:border-ink"
            />
          </div>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-soft">
              Action
            </label>
            <select
              value={shouldArchive ? 'archive' : 'keep'}
              onChange={(e) => setShouldArchive(e.target.value === 'archive')}
              className="w-full rounded-md border border-border bg-paper px-2 py-1.5 text-sm"
            >
              <option value="archive">Archive it</option>
              <option value="keep">Keep it visible</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-soft">
              Urgency
            </label>
            <select
              value={urgency}
              onChange={(e) => setUrgency(e.target.value)}
              className="w-full rounded-md border border-border bg-paper px-2 py-1.5 text-sm"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleCreate}
          disabled={saving || !matchValue.trim()}
          className="rounded-md bg-rust px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Add rule
        </button>
      </div>

      {error && <div className="mb-4 text-rust">{error}</div>}

      {rules.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border px-5 py-8 text-center text-ink-soft">
          No rules yet.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {rules.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-3"
            >
              <div className="text-sm">
                When <span className="font-medium">{r.match_field}</span> contains{' '}
                <span className="font-mono text-rust">"{r.match_value}"</span>
              </div>
              <div className="flex items-center gap-3">
                <UrgencyBadge urgency={r.urgency} />
                <span className="text-sm text-ink-soft">
                  {r.should_archive ? 'archive' : 'keep visible'}
                </span>
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-sm text-ink-soft hover:text-rust"
                  title="Delete rule"
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
