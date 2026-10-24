// On a film's page: Watched / Plan to watch / Not in a list, and for a watched film the date (today unless
// changed) and your 10-star rating. Logged out, a click opens the login dialog and completes after it.
import { BookmarkIcon, CheckIcon, MinusIcon } from 'lucide-react'

import type { EntryRequest, Status } from '@/api/client'
import { useListChange, useStatuses, todayIso } from '@/me/hooks'
import { StarRating } from '@/me/StarRating'
import { cn } from '@/lib/utils'

const CHOICES: { value: Status | 'none'; label: string; icon: typeof CheckIcon }[] = [
  { value: 'watched', label: 'Watched', icon: CheckIcon },
  { value: 'plan_to_watch', label: 'Plan to watch', icon: BookmarkIcon },
  { value: 'none', label: 'Not in a list', icon: MinusIcon },
]

export function ListControl({ movieId }: { movieId: number }) {
  const entry = useStatuses([movieId]).get(movieId)
  const change = useListChange()
  const current = entry?.status ?? 'none'
  // only the field that changed: the server keeps the others (so a click queued before a login loses nothing)
  const watched = (patch: Partial<EntryRequest>) => change(movieId, { status: 'watched', ...patch }, entry)
  const choose = (value: Status | 'none') => {
    if (value === current) return
    if (value === 'watched') watched({})
    else change(movieId, value === 'none' ? null : { status: 'plan_to_watch' }, entry)
  }

  return (
    <div className="grid gap-3" data-testid="list-control">
      <div role="radiogroup" aria-label="Your lists" className="bg-muted inline-flex w-fit flex-wrap rounded-md p-0.5 text-sm">
        {CHOICES.map(({ value, label, icon: Icon }) => (
          <button key={value} type="button" role="radio" aria-checked={current === value} onClick={() => choose(value)}
            className={cn('inline-flex items-center gap-1.5 rounded px-3 py-1.5',
              current === value ? 'bg-background font-medium shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
            <Icon aria-hidden className={cn('size-4', current === value && value === 'watched' && 'text-emerald-600',
              current === value && value === 'plan_to_watch' && 'fill-current text-sky-600')} />
            {label}
          </button>
        ))}
      </div>
      {entry?.status === 'watched' && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Watched on</span>
            <input type="date" value={entry.watched_on ?? ''} max={todayIso()} min="1900-01-01"
              onChange={e => { if (e.target.value) watched({ watched_on: e.target.value }) }}
              className="border-input bg-card dark:bg-input/30 h-8 rounded-md border px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring" />
          </label>
          <StarRating value={entry.rating} onChange={rating => watched({ rating })} />
        </div>
      )}
    </div>
  )
}
