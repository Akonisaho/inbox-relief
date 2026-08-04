import { useState } from 'react'
import { api, type NeverRepliedSender } from '../api'

export function SuggestedRules({ onApplied }: { onApplied: () => void }) {
  const [senders, setSenders] = useState<NeverRepliedSender[] | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const find = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.neverRepliedSenders(2)
      setSenders(res.senders)
      setSelected(new Set(res.senders.map((s) => s.sender)))
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const toggle = (sender: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(sender)) next.delete(sender)
      else next.add(sender)
      return next
    })
  }

  const apply = async () => {
    if (selected.size === 0) return
    setApplying(true)
    setError(null)
    try {
      await api.applyNeverReplied(Array.from(selected))
      setSenders(null)
      onApplied()
    } catch (e) {
      setError(String(e))
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="mb-8 rounded-lg border border-border bg-surface p-4">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">
          Suggested: senders you never reply to
        </h2>
        {!senders && (
          <button
            onClick={find}
            disabled={loading}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-paper disabled:opacity-50"
          >
            {loading ? 'Scanning your mailbox…' : 'Find them'}
          </button>
        )}
      </div>
      <p className="mb-3 text-xs text-ink-soft">
        Learned from your actual reply history — senders where you've never sent a message in
        any of their threads, at least twice. Review and pick which ones to turn into archive
        rules; nothing is applied automatically.
      </p>

      {error && <div className="text-rust">{error}</div>}

      {senders && senders.length === 0 && (
        <div className="text-sm text-ink-soft">No qualifying senders found.</div>
      )}

      {senders && senders.length > 0 && (
        <>
          <ul className="mb-3 max-h-64 overflow-y-auto rounded-md border border-border">
            {senders.map((s) => (
              <li key={s.sender} className="flex items-center gap-2 border-b border-border px-3 py-2 last:border-b-0">
                <input
                  type="checkbox"
                  checked={selected.has(s.sender)}
                  onChange={() => toggle(s.sender)}
                  className="shrink-0"
                />
                <span className="min-w-0 flex-1 truncate text-sm">{s.sender}</span>
                <span className="shrink-0 text-xs text-ink-soft">{s.count} emails</span>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-3">
            <button
              onClick={apply}
              disabled={applying || selected.size === 0}
              className="rounded-md bg-rust px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Archive future mail from {selected.size} selected
            </button>
            <button onClick={() => setSenders(null)} className="text-xs text-ink-soft hover:text-rust">
              Dismiss
            </button>
          </div>
        </>
      )}
    </div>
  )
}
