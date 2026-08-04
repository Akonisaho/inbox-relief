import { useEffect, useMemo, useState } from 'react'
import { api, type CalendarDayEmail } from '../api'
import { UrgencyBadge } from './Badge'
import { EmailExpando } from './EmailExpando'

export type DayFilter = 'all' | 'high' | 'archived' | 'unread'

const FILTER_LABELS: Record<DayFilter, string> = {
  all: 'All',
  high: 'High urgency',
  archived: 'Archived',
  unread: 'Unread',
}

export function DayDetailPanel({
  date,
  filter,
  onFilterChange,
  onClose,
}: {
  date: string
  filter: DayFilter
  onFilterChange: (f: DayFilter) => void
  onClose: () => void
}) {
  const [emails, setEmails] = useState<CalendarDayEmail[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setEmails(null)
    api
      .calendarDay(date)
      .then((d) => setEmails(d.emails))
      .catch((e) => setError(String(e)))
  }, [date])

  const visible = useMemo(() => {
    if (!emails) return null
    switch (filter) {
      case 'high':
        return emails.filter((e) => e.urgency === 'high')
      case 'archived':
        return emails.filter((e) => e.archived_at)
      case 'unread':
        return emails.filter((e) => e.is_unread)
      default:
        return emails
    }
  }, [emails, filter])

  return (
    <div className="mt-6 rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">
          {date} — {visible ? `${visible.length} email${visible.length === 1 ? '' : 's'}` : '…'}
        </h2>
        <button onClick={onClose} className="text-sm text-ink-soft hover:text-rust">
          ✕ Close
        </button>
      </div>

      <div className="mb-3 flex gap-2">
        {(Object.keys(FILTER_LABELS) as DayFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => onFilterChange(f)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === f ? 'bg-ink text-paper' : 'bg-paper text-ink-soft border border-border'
            }`}
          >
            {FILTER_LABELS[f]}
          </button>
        ))}
      </div>

      {error && <div className="text-rust">{error}</div>}
      {!visible && !error && <div className="text-sm text-ink-soft">Loading…</div>}

      {visible && visible.length === 0 && (
        <div className="text-sm text-ink-soft">No emails match this filter.</div>
      )}

      {visible && visible.length > 0 && (
        <ul className="flex flex-col gap-2">
          {visible.map((e) => (
            <li key={e.id} className="rounded-md border border-border bg-paper px-3 py-2">
              <div className="flex items-center gap-2">
                <UrgencyBadge urgency={e.urgency} />
                {e.archived_at && <span className="text-xs text-moss">archived</span>}
                {e.is_unread && <span className="text-xs text-rust">unread</span>}
                <span className="truncate text-sm font-medium">{e.subject}</span>
              </div>
              <div className="text-xs text-ink-soft">{e.sender}</div>
              <div className="mt-1">
                <EmailExpando emailId={e.id} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
