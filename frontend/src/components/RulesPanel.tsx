import { useEffect, useState } from 'react'
import { api, type Rule } from '../api'
import { UrgencyBadge } from './Badge'
import { SuggestedRules } from './SuggestedRules'

export function RulesPanel() {
  const [rules, setRules] = useState<Rule[]>([])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [freeText, setFreeText] = useState('')
  const [showManualForm, setShowManualForm] = useState(false)
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<string | null>(null)

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

  const handleCreateFromText = async () => {
    if (!freeText.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.createRuleFromText(freeText.trim())
      setFreeText('')
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const handleCreateManual = async () => {
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

  const handleApplyNow = async () => {
    setApplying(true)
    setApplyResult(null)
    setError(null)
    try {
      const res = await api.applyRulesNow()
      setApplyResult(`Matched ${res.matched} existing emails, archived ${res.archived} of them.`)
    } catch (e) {
      setError(String(e))
    } finally {
      setApplying(false)
    }
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Rules</h1>
      <p className="mb-4 text-sm text-ink-soft">
        Standing policies that skip classification entirely when matched. Just write what you
        mean — e.g. "emails from Acme Corp or acme@example.com are not important, archive them".
      </p>

      <div className="mb-6 rounded-lg border border-border bg-surface p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium">Apply rules to existing mail</div>
            <p className="text-xs text-ink-soft">
              New rules only affect future classification by default — this sweeps every
              unclassified email against your current rules right now (no LLM, so it's fast)
              and archives whatever matches.
            </p>
          </div>
          <button
            onClick={handleApplyNow}
            disabled={applying}
            className="shrink-0 rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-soft disabled:opacity-50"
          >
            {applying ? 'Applying…' : 'Apply now'}
          </button>
        </div>
        {applyResult && <div className="mt-2 text-sm text-moss">{applyResult}</div>}
      </div>

      <SuggestedRules onApplied={load} />

      <div className="mb-8 rounded-lg border border-border bg-surface p-4">
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-soft">
          Write a rule
        </label>
        <textarea
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder='e.g. "always archive mail from noreply@x.com" or "anything from my old landlord is not important"'
          rows={2}
          className="mb-3 w-full resize-none rounded-md border border-border bg-paper px-3 py-2 text-sm outline-none focus:border-ink"
        />
        <div className="flex items-center justify-between">
          <button
            onClick={handleCreateFromText}
            disabled={saving || !freeText.trim()}
            className="rounded-md bg-rust px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Add rule
          </button>
          <button
            onClick={() => setShowManualForm((v) => !v)}
            className="text-xs text-ink-soft underline decoration-dotted hover:text-rust"
          >
            {showManualForm ? 'Hide manual form' : 'Prefer to fill in fields manually?'}
          </button>
        </div>

        {showManualForm && (
          <div className="mt-4 border-t border-border pt-4">
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
              onClick={handleCreateManual}
              disabled={saving || !matchValue.trim()}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-paper disabled:opacity-50"
            >
              Add rule (manual)
            </button>
          </div>
        )}
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
                {r.source_text ? (
                  <span className="italic text-ink-soft">"{r.source_text}"</span>
                ) : (
                  <>
                    When <span className="font-medium">{r.match_field}</span> contains{' '}
                    <span className="font-mono text-rust">"{r.match_value}"</span>
                  </>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-3">
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
