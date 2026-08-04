export function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-5 py-4">
      <div className="text-2xl font-semibold tabular-nums text-ink">{value}</div>
      <div className="mt-1 text-sm text-ink-soft">{label}</div>
    </div>
  )
}
