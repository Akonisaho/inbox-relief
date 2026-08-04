export interface ClassifiedEmail {
  id: number
  provider_message_id: string
  subject: string
  sender: string
  urgency: 'high' | 'medium' | 'low' | null
  should_archive: boolean | null
  confidence: number | null
  reasoning: string | null
  archived_at: string | null
}

export interface DigestEmail {
  id: number
  provider_message_id: string
  subject: string
  sender: string
  urgency: string
  reasoning: string | null
  received_at: string
}

export interface Digest {
  mailbox_total: number
  archived_total: number
  inbox_count: number
  unclassified_total: number
  declutter_kb_approx: number
  needs_attention: DigestEmail[]
}

export interface EmailSummary {
  id: number
  provider: string
  subject: string
  sender: string
  received_at: string
  is_unread: boolean
  archived_at: string | null
}

export interface Rule {
  id: number
  match_field: 'sender' | 'subject'
  match_value: string
  should_archive: boolean
  urgency: string
}

export interface ChatResponse {
  intent: 'correction' | 'rule' | 'question'
  answer?: string
  rule?: Record<string, unknown>
  applied_to_email_id?: number
  error?: string
}

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export function gmailLink(providerMessageId: string): string {
  return `https://mail.google.com/mail/u/0/#all/${providerMessageId}`
}

export const api = {
  digest: () => request<Digest>('/digest'),
  emails: () => request<EmailSummary[]>('/emails'),
  classifiedEmails: () => request<ClassifiedEmail[]>('/emails/classified'),
  search: (q: string, limit = 8) =>
    request<{ query: string; results: unknown[] }>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  archive: (id: number) => request<{ archived: boolean }>(`/emails/${id}/archive`, { method: 'POST' }),
  restore: (id: number) => request<{ restored: boolean }>(`/emails/${id}/restore`, { method: 'POST' }),
  correct: (id: number, field: 'should_archive' | 'urgency', correctedValue: string, note?: string) =>
    request<{ corrected: boolean }>(`/emails/${id}/correct`, {
      method: 'POST',
      body: JSON.stringify({ field, corrected_value: correctedValue, note }),
    }),
  chat: (message: string, emailId?: number) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, email_id: emailId }),
    }),
  rules: () => request<Rule[]>('/rules'),
  createRule: (rule: Omit<Rule, 'id'>) =>
    request<Rule>('/rules', { method: 'POST', body: JSON.stringify(rule) }),
  deleteRule: (id: number) => request<{ deleted: boolean }>(`/rules/${id}`, { method: 'DELETE' }),
}
