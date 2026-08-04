import type { ReactNode } from 'react'

export type View = 'digest' | 'inbox' | 'chat' | 'rules'

const NAV: { key: View; label: string }[] = [
  { key: 'digest', label: 'Digest' },
  { key: 'inbox', label: 'Inbox' },
  { key: 'chat', label: 'Chat' },
  { key: 'rules', label: 'Rules' },
]

export function Shell({
  active,
  onNavigate,
  children,
}: {
  active: View
  onNavigate: (v: View) => void
  children: ReactNode
}) {
  return (
    <div className="flex min-h-screen bg-paper text-ink">
      <aside className="flex w-56 shrink-0 flex-col justify-between bg-ink px-5 py-6 text-paper">
        <div>
          <div className="mb-8">
            <div className="text-lg font-semibold tracking-tight">Inbox Relief</div>
            <div className="text-xs text-paper/50">local · private · yours</div>
          </div>
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <button
                key={item.key}
                onClick={() => onNavigate(item.key)}
                className={`rounded-md px-3 py-2 text-left text-sm font-medium transition-colors ${
                  active === item.key
                    ? 'bg-rust text-white'
                    : 'text-paper/70 hover:bg-white/5 hover:text-paper'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="text-xs text-paper/40">
          Nothing archived here is ever deleted.
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto px-10 py-8">{children}</main>
    </div>
  )
}
