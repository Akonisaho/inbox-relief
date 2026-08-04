import { useEffect, useMemo, useState } from 'react'
import { api, type ClassifiedEmail } from '../api'
import { UrgencyBadge } from './Badge'
import { QuickRuleButton } from './QuickRuleButton'
import { EmailExpando } from './EmailExpando'

type Filter = 'active' | 'archived' | 'all'
type UrgencyFilter = 'all' | 'high' | 'medium' | 'low'

export function InboxView() {
  const [emails, setEmails] = useState<ClassifiedEmail[]>([])
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('active')
  const [urgencyFilter, setUrgencyFilter] = useState<UrgencyFilter>('all')
  const [query, setQuery] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = () => {
    api
      .classifiedEmails()
      .then(setEmails)
      .catch((e) => setError(String(e)))
  }

  useEffect(load, [])

  const visible = useMemo(() => {
    let list = emails
    if (filter === 'active') list = list.filter((e) => !e.archived_at)
    if (filter === 'archived') list = list.filter((e) => e.archived_at)
    if (urgencyFilter !== 'all') list = list.filter((e) => e.urgency === urgencyFilter)
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(
        (e) => e.subject.toLowerCase().includes(q) || e.sender.toLowerCase().includes(q),
      )
    }
    return list
  }, [emails, filter, urgencyFilter, query])

  const withBusy = async (id: number, fn: () => Promise<unknown>) => {
    setBusyId(id)
    try {
      await fn()
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Inbox</h1>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by subject or sender…"
          className="w-72 rounded-md border border-border bg-surface px-3 py-1.5 text-sm outline-none focus:border-ink"
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-4">
        <div className="flex gap-2">
          {(['active', 'archived', 'all'] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full px-3 py-1 text-sm font-medium capitalize ${
                filter === f ? 'bg-ink text-paper' : 'bg-surface text-ink-soft border border-border'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <div className="h-5 w-px bg-border" />
        <div className="flex gap-2">
          {(['all', 'high', 'medium', 'low'] as UrgencyFilter[]).map((u) => (
            <button
              key={u}
              onClick={() => setUrgencyFilter(u)}
              className={`rounded-full px-3 py-1 text-sm font-medium capitalize ${
                urgencyFilter === u ? 'bg-ink text-paper' : 'bg-surface text-ink-soft border border-border'
              }`}
            >
              {u === 'all' ? 'Any urgency' : u}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="mb-4 text-rust">{error}</div>}

      <ul className="flex flex-col gap-2">
        {visible.map((e) => (
          <li
            key={e.id}
            className="flex items-start justify-between gap-4 rounded-lg border border-border bg-surface px-4 py-3"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <UrgencyBadge urgency={e.urgency} />
                {e.archived_at && (
                  <span className="text-xs text-ink-soft">archived</span>
                )}
                <span className="truncate font-medium">{e.subject}</span>
              </div>
              <div className="text-sm text-ink-soft">{e.sender}</div>
              <div className="mt-1 flex items-center gap-3">
                <EmailExpando emailId={e.id} />
                <QuickRuleButton sender={e.sender} />
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              {e.archived_at ? (
                <button
                  disabled={busyId === e.id}
                  onClick={() => withBusy(e.id, () => api.restore(e.id))}
                  className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-paper disabled:opacity-50"
                >
                  Restore
                </button>
              ) : (
                <button
                  disabled={busyId === e.id}
                  onClick={() => withBusy(e.id, () => api.archive(e.id))}
                  className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-paper hover:bg-ink-soft disabled:opacity-50"
                >
                  Archive
                </button>
              )}
            </div>
          </li>
        ))}
        {visible.length === 0 && (
          <li className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-ink-soft">
            No emails match this view.
          </li>
        )}
      </ul>
    </div>
  )
}
