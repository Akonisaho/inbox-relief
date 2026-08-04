const STYLES: Record<string, string> = {
  high: 'bg-rust-soft text-rust border-rust/30',
  medium: 'bg-amber-soft text-amber border-amber/30',
  low: 'bg-moss-soft text-moss border-moss/30',
}

export function UrgencyBadge({ urgency }: { urgency: string | null }) {
  if (!urgency) {
    return (
      <span className="inline-flex items-center rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs font-medium text-ink-soft">
        unclassified
      </span>
    )
  }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${STYLES[urgency] ?? STYLES.low}`}
    >
      {urgency}
    </span>
  )
}
