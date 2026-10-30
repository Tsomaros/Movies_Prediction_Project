// The New arrivals row (V1.2), the first row of /movies: a CuratedRow whose header holds a Just released | Coming soon
// switch (default Just released; the choice is kept for the visit in sessionStorage, which can fail, so every
// access is wrapped). "See all" opens the same window on /browse. The switch is a radio group: ← and → move.
import { useRef, useState, type KeyboardEvent } from 'react'

import { cn } from '@/lib/utils'
import { CuratedRow } from '@/movies/CuratedRow'
import { NEW_ROWS } from '@/movies/rows'

type Window = keyof typeof NEW_ROWS
const KEY = 'movie-prediction:new-arrivals'
const CHOICES: { value: Window; label: string }[] = [{ value: 'released', label: 'Just released' }, { value: 'upcoming', label: 'Coming soon' }]
const EMPTY: Record<Window, string> = {
  released: 'No new films in the last two weeks yet.',
  upcoming: 'Nothing announced for the next two months yet.',
}

function load(): Window {
  try {
    return sessionStorage.getItem(KEY) === 'upcoming' ? 'upcoming' : 'released'
  } catch {
    return 'released'
  }
}

function save(value: Window) {
  try {
    sessionStorage.setItem(KEY, value)
  } catch { /* blocked storage: the choice lasts until the page is left */ }
}

function Switch({ value, onChange }: { value: Window; onChange: (w: Window) => void }) {
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})
  const onKeyDown = (e: KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return
    e.preventDefault()
    const next: Window = value === 'released' ? 'upcoming' : 'released'
    onChange(next)
    buttons.current[next]?.focus()
  }
  return (
    <div role="radiogroup" aria-label="New arrivals" className="bg-muted inline-flex rounded-md p-0.5">
      {CHOICES.map(c => (
        <button key={c.value} ref={el => { buttons.current[c.value] = el }} type="button" role="radio" aria-checked={c.value === value}
          tabIndex={c.value === value ? 0 : -1} onClick={() => onChange(c.value)} onKeyDown={onKeyDown}
          className={cn('rounded px-2.5 py-1 text-xs font-medium outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50',
            c.value === value ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
          {c.label}
        </button>
      ))}
    </div>
  )
}

export function NewArrivalsRow() {
  const [window, setWindow] = useState<Window>(load)
  const choose = (w: Window) => { setWindow(w); save(w) }
  return <CuratedRow row={NEW_ROWS[window]} first header={<Switch value={window} onChange={choose} />} emptyText={EMPTY[window]} />
}
