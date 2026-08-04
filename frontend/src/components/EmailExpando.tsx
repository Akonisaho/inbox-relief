import { useState } from 'react'
import { api, gmailLink } from '../api'

export function EmailExpando({ emailId }: { emailId: number }) {
  const [open, setOpen] = useState(false)
  const [body, setBody] = useState<string | null>(null)
  const [messageIdHeader, setMessageIdHeader] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggle = async () => {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (body !== null) return // already fetched
    setLoading(true)
    try {
      const detail = await api.emailDetail(emailId)
      setBody(detail.body_text)
      setMessageIdHeader(detail.message_id_header)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <button
        onClick={toggle}
        className="text-xs font-medium text-ink-soft underline decoration-dotted hover:text-rust"
      >
        {open ? 'Hide' : 'Read email'}
      </button>

      {open && (
        <div className="mt-2 rounded-md border border-border bg-paper p-3">
          {loading && <div className="text-sm text-ink-soft">Loading…</div>}
          {error && <div className="text-sm text-rust">{error}</div>}
          {body !== null && (
            <>
              <div className="mb-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-sm text-ink-soft">
                {body || '(no content)'}
              </div>
              <a
                href={gmailLink(messageIdHeader)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-md bg-rust px-3 py-1.5 text-xs font-medium text-white hover:bg-rust/90"
              >
                ↩ Reply in Gmail
              </a>
            </>
          )}
        </div>
      )}
    </div>
  )
}
