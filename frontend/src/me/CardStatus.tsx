// A film card's list status, for a logged-in visitor: a badge on the poster (a check for watched, with your
// rating; a bookmark for the watchlist; always with a text label, not colour alone) and two quick buttons that
// appear on hover or focus on devices with a mouse. Phones show the badge only.
import { BookmarkIcon, CheckIcon } from 'lucide-react'

import type { Entry } from '@/api/client'
import { useListChange } from '@/me/hooks'
import { cn } from '@/lib/utils'

export function StatusBadge({ entry }: { entry: Entry }) {
  const watched = entry.status === 'watched'
  const label = watched ? `Watched${entry.rating ? `, rated ${entry.rating}/10` : ''}` : 'On your watchlist'
  return (
    <span title={label} data-testid="status-badge"
      className={cn('absolute top-1.5 left-1.5 inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold text-white shadow',
        watched ? 'bg-emerald-700' : 'bg-sky-700')}>
      {watched ? <CheckIcon aria-hidden className="size-3" /> : <BookmarkIcon aria-hidden className="size-3 fill-current" />}
      {watched && entry.rating ? <span aria-hidden>{entry.rating}</span> : null}
      <span className="sr-only">{label}</span>
    </span>
  )
}

const QUICK = 'inline-flex size-8 items-center justify-center rounded-full shadow backdrop-blur focus-visible:outline-2 focus-visible:outline-ring'

export function QuickButtons({ movieId, title, entry }: { movieId: number; title: string; entry?: Entry }) {
  const change = useListChange()
  const watched = entry?.status === 'watched'
  const planned = entry?.status === 'plan_to_watch'
  return (
    <div className="pointer-fine:flex absolute top-1.5 right-1.5 hidden gap-1 opacity-0 transition-opacity group-hover/card:opacity-100 focus-within:opacity-100">
      <button type="button" aria-pressed={watched} aria-label={`Watched: ${title}`} title={watched ? 'Remove from watched' : 'Mark as watched'}
        onClick={() => change(movieId, watched ? null : { status: 'watched' }, entry)}
        className={cn(QUICK, watched ? 'bg-emerald-700 text-white' : 'bg-background/90 text-foreground hover:bg-background')}>
        <CheckIcon aria-hidden className="size-4" />
      </button>
      <button type="button" aria-pressed={planned} aria-label={`Plan to watch: ${title}`} title={planned ? 'Remove from watchlist' : 'Add to watchlist'}
        onClick={() => change(movieId, planned ? null : { status: 'plan_to_watch' }, entry)}
        className={cn(QUICK, planned ? 'bg-sky-700 text-white' : 'bg-background/90 text-foreground hover:bg-background')}>
        <BookmarkIcon aria-hidden className={cn('size-4', planned && 'fill-current')} />
      </button>
    </div>
  )
}
