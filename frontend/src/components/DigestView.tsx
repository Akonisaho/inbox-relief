import { useEffect, useState } from 'react'
import { api, gmailLink, type Digest } from '../api'
import { StatCard } from './StatCard'
import { UrgencyBadge } from './Badge'
import { QuickRuleButton } from './QuickRuleButton'

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

      <div className="mb-2 grid grid-cols-4 gap-4">
        <StatCard label="In your inbox view" value={digest.inbox_count} />
        <StatCard label="Archived so far" value={digest.archived_total} />
        <StatCard label="Decluttered from view" value={declutterLabel} />
        <StatCard label="Awaiting classification" value={digest.unclassified_total} />
      </div>
      <p className="mb-8 text-xs text-ink-soft">
        Archiving hides mail from your Gmail inbox but never deletes it — Gmail's storage quota
        counts archived mail the same as inbox mail, so this reflects inbox clutter reduced, not
        storage freed.
      </p>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-soft">
        Needs your attention
      </h2>

      {digest.needs_attention.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-surface px-5 py-8 text-center text-ink-soft">
          Nothing needs attention right now.
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {digest.needs_attention.map((e) => (
            <li key={e.id} className="rounded-lg border border-border bg-surface p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <UrgencyBadge urgency={e.urgency} />
                    <a
                      href={gmailLink(e.provider_message_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate font-medium hover:text-rust hover:underline"
                    >
                      {e.subject}
                    </a>
                  </div>
                  <div className="mt-1 text-sm text-ink-soft">{e.sender}</div>
                  {e.reasoning && (
                    <div className="mt-2 text-sm italic text-ink-soft">"{e.reasoning}"</div>
                  )}
                  <div className="mt-2">
                    <QuickRuleButton sender={e.sender} />
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    disabled={busyId === e.id}
                    onClick={() => handleNotArchivable(e.id)}
                    className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-ink-soft hover:bg-paper disabled:opacity-50"
                  >
                    Keep visible
                  </button>
                  <button
                    disabled={busyId === e.id}
                    onClick={() => handleArchive(e.id)}
                    className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-paper hover:bg-ink-soft disabled:opacity-50"
                  >
                    Archive
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
