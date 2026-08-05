import { useEffect, useState } from 'react'
import { api, type Digest, type DigestEmail } from '../api'
import { StatCard } from './StatCard'
import { DueDateBadge, UrgencyBadge } from './Badge'
import { QuickRuleButton } from './QuickRuleButton'
import { EmailExpando } from './EmailExpando'
import { StorageBar } from './StorageBar'

function EmailCard({
  e,
  busy,
  onArchive,
  onKeepVisible,
}: {
  e: DigestEmail
  busy: boolean
  onArchive: () => void
  onKeepVisible: () => void
}) {
  return (
    <li className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <UrgencyBadge urgency={e.urgency} />
            <DueDateBadge dueDate={e.due_date} />
            <span className="truncate font-medium">{e.subject}</span>
          </div>
          <div className="mt-1 text-sm text-ink-soft">{e.sender}</div>
          {e.snippet && <div className="mt-2 text-sm text-ink-soft">{e.snippet}</div>}
          {e.reasoning && (
            <div className="mt-1 text-xs italic text-ink-soft/70">Why: {e.reasoning}</div>
          )}
          <div className="mt-2 flex items-center gap-3">
            <EmailExpando emailId={e.id} />
            <QuickRuleButton sender={e.sender} />
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            disabled={busy}
            onClick={onKeepVisible}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-ink-soft hover:bg-paper disabled:opacity-50"
          >
            Keep visible
          </button>
          <button
            disabled={busy}
            onClick={onArchive}
            className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-paper hover:bg-ink-soft disabled:opacity-50"
          >
            Archive
          </button>
        </div>
      </div>
    </li>
  )
}

export function DigestView() {
  const [digest, setDigest] = useState<Digest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = () => {
    api
      .digest()
      .then(setDigest)
      .catch((e) => setError(String(e)))
  }

  useEffect(load, [])

  const handleArchive = async (id: number) => {
    setBusyId(id)
    try {
      await api.archive(id)
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusyId(null)
    }
  }

  const handleNotArchivable = async (id: number) => {
    setBusyId(id)
    try {
      await api.correct(id, 'should_archive', 'false', 'marked as not archivable from digest')
      load()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusyId(null)
    }
  }

  if (error) return <div className="text-rust">Couldn't load digest: {error}</div>
  if (!digest) return <div className="text-ink-soft">Loading digest…</div>

  const declutterLabel =
    digest.declutter_kb_approx > 1024
      ? `${(digest.declutter_kb_approx / 1024).toFixed(1)} MB`
      : `${digest.declutter_kb_approx.toFixed(0)} KB`

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Today's Digest</h1>

      <StorageBar />

      <div className="mb-2 grid grid-cols-5 gap-4">
        <StatCard label="Received today" value={digest.received_today} />
        <StatCard label="Total in mailbox" value={digest.mailbox_total} />
        <StatCard label="Remaining in inbox" value={digest.inbox_count} />
        <StatCard label="Archived so far" value={digest.archived_total} />
        <StatCard label="Awaiting classification" value={digest.unclassified_total} />
      </div>
      <p className="mb-8 text-xs text-ink-soft">
        Archived mail is removed from "Remaining in inbox" ({declutterLabel} of content
        decluttered from view so far) but Gmail's storage quota counts archived mail the same as
        inbox mail — archiving reduces clutter, not your storage usage.
      </p>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-rust">
        Needs immediate attention {digest.needs_immediate_attention.length > 0 && `(${digest.needs_immediate_attention.length})`}
      </h2>
      {digest.needs_immediate_attention.length === 0 ? (
        <div className="mb-8 rounded-lg border border-dashed border-border bg-surface px-5 py-6 text-center text-ink-soft">
          Nothing urgent today.
        </div>
      ) : (
        <ul className="mb-8 flex flex-col gap-3">
          {digest.needs_immediate_attention.map((e) => (
            <EmailCard
              key={e.id}
              e={e}
              busy={busyId === e.id}
              onArchive={() => handleArchive(e.id)}
              onKeepVisible={() => handleNotArchivable(e.id)}
            />
          ))}
        </ul>
      )}

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-amber">
        Important today {digest.important_today.length > 0 && `(${digest.important_today.length})`}
      </h2>
      {digest.important_today.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-surface px-5 py-6 text-center text-ink-soft">
          Nothing else important today.
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {digest.important_today.map((e) => (
            <EmailCard
              key={e.id}
              e={e}
              busy={busyId === e.id}
              onArchive={() => handleArchive(e.id)}
              onKeepVisible={() => handleNotArchivable(e.id)}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
