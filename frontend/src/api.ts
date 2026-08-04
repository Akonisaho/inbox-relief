export interface ClassifiedEmail {
  id: number
  provider_message_id: string
  message_id_header: string
  subject: string
  sender: string
  urgency: 'high' | 'medium' | 'low' | null
  should_archive: boolean | null
  confidence: number | null
  reasoning: string | null
  due_date: string | null
  archived_at: string | null
}

export interface DigestEmail {
  id: number
  provider_message_id: string
  message_id_header: string
  subject: string
  sender: string
  snippet: string
  urgency: string
  reasoning: string | null
  due_date: string | null
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

export interface EmailDetail {
  id: number
  message_id_header: string
  subject: string
  sender: string
  recipients: string[]
  received_at: string
  body_text: string
  urgency: string | null
  should_archive: boolean | null
  reasoning: string | null
  due_date: string | null
  archived_at: string | null
}

export interface CalendarDay {
  date: string
  received: number
  archived: number
  unread: number
  high: number
}

export interface CalendarMonth {
  year: number
  month: number
  days: CalendarDay[]
}

export interface CalendarDayEmail {
  id: number
  subject: string
  sender: string
  urgency: string | null
  is_unread: boolean
  archived_at: string | null
  received_at: string
}

export interface CalendarDayDetail {
  date: string
  emails: CalendarDayEmail[]
}

export interface NeverRepliedSender {
  sender: string
  count: number
}

export interface NeverRepliedResponse {
  own_email: string
  senders: NeverRepliedSender[]
}

export interface Rule {
  id: number
  match_field: 'sender' | 'subject'
  match_value: string
  should_archive: boolean
  urgency: string
  source_text: string | null
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

/** Reliable Gmail deep link: search by the email's true RFC822 Message-ID
 * header, not Gmail's internal API id — the internal id maps to individual
 * messages while Gmail's web UI is thread-centric, so #all/<id>-style links
 * are unreliable. Falls back to just opening the inbox if we don't have it
 * (older synced rows, before this field existed — re-sync backfills it). */
export function gmailLink(messageIdHeader: string): string {
  if (!messageIdHeader) return 'https://mail.google.com/mail/u/0/#inbox'
  return `https://mail.google.com/mail/u/0/#search/rfc822msgid:${encodeURIComponent(messageIdHeader)}`
}

export const api = {
  digest: () => request<Digest>('/digest'),
  emails: () => request<EmailSummary[]>('/emails'),
  classifiedEmails: () => request<ClassifiedEmail[]>('/emails/classified'),
  emailDetail: (id: number) => request<EmailDetail>(`/emails/${id}`),
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
  calendar: (year: number, month: number) =>
    request<CalendarMonth>(`/calendar?year=${year}&month=${month}`),
  calendarDay: (date: string) => request<CalendarDayDetail>(`/calendar/day?date=${date}`),
  createRule: (rule: Omit<Rule, 'id' | 'source_text'>) =>
    request<Rule>('/rules', { method: 'POST', body: JSON.stringify(rule) }),
  createRuleFromText: (text: string) =>
    request<Rule>('/rules/from_text', { method: 'POST', body: JSON.stringify({ text }) }),
  deleteRule: (id: number) => request<{ deleted: boolean }>(`/rules/${id}`, { method: 'DELETE' }),
  neverRepliedSenders: (minCount = 2) =>
    request<NeverRepliedResponse>(`/senders/never-replied?min_count=${minCount}`),
  applyNeverReplied: (senders: string[]) =>
    request<{ created: number }>('/senders/never-replied/apply', {
      method: 'POST',
      body: JSON.stringify({ senders }),
    }),
}
