// The picked film: poster, title, year, runtime, score with votes and genres, then what to do with it: open its
// page, or put it on a list (whole-database picks: Add to watchlist; watchlist picks: Mark as watched, which also
// takes it off the watchlist, since a film is in one list only). The list button reuses the browse cards'
// optimistic change, behind a login, and shows the film's current list.
import { BookmarkIcon, CheckIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { RandomMovie } from '@/api/client'
import { Button } from '@/components/ui/button'
import { useListChange, useStatuses } from '@/me/hooks'
import { ScoreText } from '@/movies/MovieCard'
import { runtimeText } from '@/movies/people'
import { Poster } from '@/movies/Poster'
import type { Source } from '@/surprise/prefs'

export function PickCard({ movie, pool, source, onOpen }: {
  movie: RandomMovie; pool: number; source: Source; onOpen: () => void
}) {
  const entry = useStatuses([movie.id]).get(movie.id)
  const change = useListChange()
  const watched = entry?.status === 'watched'
  const planned = entry?.status === 'plan_to_watch'
  const facts = [movie.year ?? 'Year unknown', movie.runtime ? runtimeText(movie.runtime) : null].filter(Boolean).join(' · ')
  return (
    <article aria-labelledby="pick-title" className="grid grid-cols-[7rem_1fr] gap-4 sm:grid-cols-[9rem_1fr]">
      <Poster poster={movie.poster} title={movie.title} eager />
      <div className="grid content-start gap-1.5">
        <h3 id="pick-title" className="text-lg font-semibold leading-tight">{movie.title}</h3>
        <p className="text-muted-foreground text-sm">{facts}</p>
        <p className="text-sm"><ScoreText score={movie.score} votes={movie.votes} /></p>
        <p className="text-muted-foreground text-sm">{movie.genres.join(', ') || 'No genre listed'}</p>
        <p className="text-muted-foreground text-xs" data-testid="pool">
          Picked from {pool.toLocaleString('en-US')} {pool === 1 ? 'film' : 'films'}
        </p>
        <div className="mt-1 flex flex-wrap gap-2">
          <Button asChild size="sm"><Link to={`/movies/${movie.id}`} onClick={onOpen}>Open details</Link></Button>
          {source === 'all' ? (
            <Button size="sm" variant="outline" aria-pressed={planned}
              onClick={() => change(movie.id, planned ? null : { status: 'plan_to_watch' }, entry)}>
              <BookmarkIcon aria-hidden className={planned ? 'fill-current' : undefined} />
              {planned ? 'On your watchlist' : 'Add to watchlist'}
            </Button>
          ) : (
            <Button size="sm" variant="outline" aria-pressed={watched}
              onClick={() => change(movie.id, { status: watched ? 'plan_to_watch' : 'watched' }, entry)}>
              <CheckIcon aria-hidden />
              {watched ? 'Watched' : 'Mark as watched'}
            </Button>
          )}
        </div>
      </div>
    </article>
  )
}
