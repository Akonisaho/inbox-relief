import { useState } from 'react'
import { api } from '../api'

interface Message {
  role: 'user' | 'assistant'
  text: string
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: "Ask about your inbox, correct a past judgment, or set a standing rule — e.g. \"any emails about apartments?\", \"always archive emails from noreply@x.com\".",
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)

  const send = async () => {
    const message = input.trim()
    if (!message || sending) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: message }])
    setSending(true)
    try {
      const res = await api.chat(message)
      let reply: string
      if (res.intent === 'question') {
        reply = res.answer ?? '(no answer)'
      } else if (res.intent === 'rule') {
        reply = `Got it — new rule saved: ${JSON.stringify(res.rule)}`
      } else if (res.intent === 'correction') {
        reply = res.error ?? `Applied correction to email #${res.applied_to_email_id}.`
      } else {
        reply = 'Not sure how to handle that.'
      }
      setMessages((m) => [...m, { role: 'assistant', text: reply }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${String(e)}` }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Chat</h1>

      <div className="mb-4 flex-1 space-y-3 overflow-y-auto rounded-lg border border-border bg-surface p-4">
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            <span
              className={`inline-block max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                m.role === 'user' ? 'bg-ink text-paper' : 'bg-paper text-ink border border-border'
              }`}
            >
              {m.text}
            </span>
          </div>
        ))}
        {sending && <div className="text-sm text-ink-soft">Thinking…</div>}
      </div>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Message your inbox…"
          className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-ink"
        />
        <button
          onClick={send}
          disabled={sending}
          className="rounded-md bg-rust px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
