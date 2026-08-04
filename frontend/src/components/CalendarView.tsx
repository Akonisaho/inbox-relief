import { useEffect, useMemo, useState } from 'react'
import { api, type CalendarMonth } from '../api'
import { DayDetailPanel, type DayFilter } from './DayDetailPanel'

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export function CalendarView() {
  const today = useMemo(() => new Date(), [])
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1) // 1-12
  const [data, setData] = useState<CalendarMonth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedFilter, setSelectedFilter] = useState<DayFilter>('all')

  useEffect(() => {
    api
      .calendar(year, month)
      .then(setData)
      .catch((e) => setError(String(e)))
  }, [year, month])

  const byDate = useMemo(() => {
    const map = new Map<string, { received: number; archived: number; unread: number; high: number }>()
    data?.days.forEach((d) => map.set(d.date, d))
    return map
  }, [data])

  const goPrev = () => {
    setSelectedDate(null)
    if (month === 1) { setYear((y) => y - 1); setMonth(12) } else setMonth((m) => m - 1)
  }
  const goNext = () => {
    setSelectedDate(null)
    if (month === 12) { setYear((y) => y + 1); setMonth(1) } else setMonth((m) => m + 1)
  }

  const openWith = (dateStr: string, filter: DayFilter) => {
    if (dateStr === selectedDate && filter === selectedFilter) {
      setSelectedDate(null)
    } else {
      setSelectedDate(dateStr)
      setSelectedFilter(filter)
    }
  }

  const firstOfMonth = new Date(Date.UTC(year, month - 1, 1))
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const leadingBlanks = firstOfMonth.getUTCDay()

  const cells: (number | null)[] = [
    ...Array(leadingBlanks).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  const pad = (n: number) => String(n).padStart(2, '0')

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Calendar</h1>
        <div className="flex items-center gap-3">
          <button onClick={goPrev} className="rounded-md border border-border px-2 py-1 text-sm hover:bg-surface">
            ←
          </button>
          <span className="w-36 text-center text-sm font-medium">
            {MONTH_NAMES[month - 1]} {year}
          </span>
          <button onClick={goNext} className="rounded-md border border-border px-2 py-1 text-sm hover:bg-surface">
            →
          </button>
        </div>
      </div>

      {error && <div className="mb-4 text-rust">{error}</div>}

      <div className="grid grid-cols-7 gap-2">
        {WEEKDAYS.map((w) => (
          <div key={w} className="text-center text-xs font-semibold uppercase tracking-wide text-ink-soft">
            {w}
          </div>
        ))}
        {cells.map((dayNum, i) => {
          if (dayNum === null) return <div key={`blank-${i}`} />
          const dateStr = `${year}-${pad(month)}-${pad(dayNum)}`
          const stats = byDate.get(dateStr)
          const isToday = dateStr === `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`
          const isSelected = dateStr === selectedDate
          return (
            <div
              key={dateStr}
              className={`min-h-20 rounded-md border p-2 text-left ${
                isSelected ? 'border-ink bg-ink text-paper' : isToday ? 'border-rust bg-rust-soft' : 'border-border bg-surface'
              }`}
            >
              <button
                disabled={!stats}
                onClick={() => stats && openWith(dateStr, 'all')}
                className={`text-xs font-medium ${isSelected ? 'text-paper/70' : 'text-ink-soft'} ${stats ? 'cursor-pointer hover:underline' : 'cursor-default opacity-50'}`}
              >
                {dayNum}
              </button>
              {stats ? (
                <div className="mt-1 space-y-0.5 text-xs">
                  <button onClick={() => openWith(dateStr, 'all')} className="block hover:underline">
                    {stats.received} received
                  </button>
                  {stats.high > 0 && (
                    <button
                      onClick={() => openWith(dateStr, 'high')}
                      className={`block hover:underline ${isSelected ? 'text-paper' : 'text-rust'}`}
                    >
                      {stats.high} high
                    </button>
                  )}
                  <button
                    onClick={() => openWith(dateStr, 'archived')}
                    className={`block hover:underline ${isSelected ? 'text-paper/80' : 'text-moss'}`}
                  >
                    {stats.archived} archived
                  </button>
                  <button
                    onClick={() => openWith(dateStr, 'unread')}
                    className={`block hover:underline ${isSelected ? 'text-paper/80' : 'text-rust'}`}
                  >
                    {stats.unread} unread
                  </button>
                </div>
              ) : (
                <div className="mt-1 text-xs opacity-50">—</div>
              )}
            </div>
          )
        })}
      </div>

      {selectedDate && (
        <DayDetailPanel
          date={selectedDate}
          filter={selectedFilter}
          onFilterChange={setSelectedFilter}
          onClose={() => setSelectedDate(null)}
        />
      )}
    </div>
  )
}
