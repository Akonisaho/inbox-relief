import { useEffect, useState } from 'react'
import { api, type StorageQuota } from '../api'

function formatBytes(bytes: number): string {
  const gb = bytes / 1024 ** 3
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / 1024 ** 2
  return `${mb.toFixed(0)} MB`
}

export function StorageBar() {
  const [quota, setQuota] = useState<StorageQuota | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .storage()
      .then(setQuota)
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return null // non-critical stat — fail quietly rather than break the dashboard
  if (!quota) return null

  const percent = quota.percent_used ?? 0

  return (
    <div className="mb-6 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-4">
        <span className="shrink-0 text-sm font-medium text-ink-soft">Mailbox storage</span>
        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-rust transition-all"
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
        <span className="shrink-0 text-lg font-bold text-ink">{percent}%</span>
      </div>
      {quota.limit_bytes && (
        <div className="mt-1 text-xs text-ink-soft">
          {formatBytes(quota.used_bytes)} of {formatBytes(quota.limit_bytes)} used — archiving
          doesn't change this (Gmail counts archived mail the same as inbox mail)
        </div>
      )}
    </div>
  )
}
