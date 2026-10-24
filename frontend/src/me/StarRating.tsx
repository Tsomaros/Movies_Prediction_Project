// Your rating of a watched film: 10 stars (the TMDB 0-10 scale), shown as "8/10". A radio group: Tab reaches it
// once, the arrow keys move the rating (each star announces "8 out of 10"), Home/End jump to 1 and 10, and
// Delete clears it; clicking the current star clears it too. A click saves at once; the keys move the stars at
// once but save only after KEY_SAVE_MS without a key (or when focus leaves), so 7 presses make one request.
import { StarIcon } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

import { cn } from '@/lib/utils'

const STARS = Array.from({ length: 10 }, (_, i) => i + 1)
export const KEY_SAVE_MS = 600

export function StarRating({ value, onChange, disabled = false }: {
  value: number | null; onChange: (rating: number | null) => void; disabled?: boolean
}) {
  const [hover, setHover] = useState<number | null>(null)
  const [draft, setDraft] = useState<{ rating: number | null } | null>(null) // keyed but not yet saved
  const stars = useRef<(HTMLButtonElement | null)[]>([])
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const current = draft ? draft.rating : value
  const shown = hover ?? current ?? 0

  const save = (rating: number | null) => {
    clearTimeout(timer.current)
    setDraft(null)
    if (rating !== value) onChange(rating)
  }
  useEffect(() => () => clearTimeout(timer.current), [])

  const key = (rating: number | null) => {
    setDraft({ rating })
    if (rating !== null) stars.current[rating - 1]?.focus()
    clearTimeout(timer.current)
    timer.current = setTimeout(() => save(rating), KEY_SAVE_MS)
  }
  const onKeyDown = (e: KeyboardEvent) => {
    const step = (by: number) => key(Math.min(10, Math.max(1, (current ?? (by > 0 ? 0 : 2)) + by)))
    const keys: Record<string, () => void> = {
      ArrowRight: () => step(1), ArrowUp: () => step(1), ArrowLeft: () => step(-1), ArrowDown: () => step(-1),
      Home: () => key(1), End: () => key(10), Delete: () => key(null), Backspace: () => key(null),
    }
    if (keys[e.key]) {
      e.preventDefault()
      keys[e.key]()
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div role="radiogroup" aria-label="Your rating" className="flex" onMouseLeave={() => setHover(null)}
        onBlur={e => { if (draft && !e.currentTarget.contains(e.relatedTarget)) save(draft.rating) }}>
        {STARS.map(n => (
          <button key={n} ref={el => { stars.current[n - 1] = el }} type="button" role="radio" disabled={disabled}
            aria-checked={current === n} aria-label={`${n} out of 10`} tabIndex={n === (current ?? 1) ? 0 : -1}
            onClick={() => save(current === n ? null : n)} onMouseEnter={() => setHover(n)} onKeyDown={onKeyDown}
            className="rounded p-0.5 focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50">
            <StarIcon aria-hidden className={cn('size-5 transition-colors',
              n <= shown ? 'fill-amber-400 text-amber-500' : 'text-muted-foreground/40')} />
          </button>
        ))}
      </div>
      <span className="text-sm font-medium tabular-nums" data-testid="your-rating">{current ? `${current}/10` : 'Not rated'}</span>
    </div>
  )
}
