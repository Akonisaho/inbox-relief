import { useState } from 'react'
import { api } from '../api'

function extractSenderAddress(sender: string): string {
  const match = sender.match(/<([^>]+)>/)
  return match ? match[1] : sender
}

export function QuickRuleButton({ sender }: { sender: string }) {
  const [state, setState] = useState<'idle' | 'saving' | 'done'>('idle')
  const address = extractSenderAddress(sender)

  if (state === 'done') {
    return <span className="text-xs text-moss">Rule added — future mail from this sender auto-archives</span>
  }

  return (
    <button
      disabled={state === 'saving'}
      onClick={async () => {
        setState('saving')
        try {
          await api.createRule({
            match_field: 'sender',
            match_value: address,
            should_archive: true,
            urgency: 'low',
          })
          setState('done')
        } catch {
          setState('idle')
        }
      }}
      className="text-xs text-ink-soft underline decoration-dotted hover:text-rust disabled:opacity-50"
    >
      + Always archive mail from {address}
    </button>
  )
}
