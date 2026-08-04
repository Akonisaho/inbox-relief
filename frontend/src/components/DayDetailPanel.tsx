import { useEffect, useState } from 'react'
import { api, type CalendarDayEmail } from '../api'
import { UrgencyBadge } from './Badge'
import { EmailExpando } from './EmailExpando'

export function DayDetailPanel({ date, onClose }: { date: string; onClose: () => void }) {
  const [emails, setEmails] = useState<CalendarDayEmail[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setEmails(null)
    api
      .calendarDay(date)
      .then((d) => setEmails(d.emails))
      .catch((e) => setError(String(e)))
  }, [date])

  return (
    <div className="mt-6 rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-soft">
          {date} — {emails ? `${emails.length} email${emails.length === 1 ? '' : 's'}` : '…'}
        </h2>
        <button onClick={onClose} className="text-sm text-ink-soft hover:text-rust">
          ✕ Close
        </button>
      </div>

      {error && <div className="text-rust">{error}</div>}
      {!emails && !error && <div className="text-sm text-ink-soft">Loading…</div>}

      {emails && emails.length === 0 && (
        <div className="text-sm text-ink-soft">No emails on this day.</div>
      )}

      {emails && emails.length > 0 && (
        <ul className="flex flex-col gap-2">
          {emails.map((e) => (
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
