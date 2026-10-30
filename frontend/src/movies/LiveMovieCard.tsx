// One live new or upcoming film (V1.2): poster with a text badge ("Out today", "New" or the release date), title
// and a footer (score, "Not rated yet" or "Coming Nov 14"). A film already in our database links to its page;
// any other opens the quick-view modal (?film=). `size` small is the "Coming soon" strip.
import { Link } from 'react-router'

import type { LiveMovie } from '@/api/client'
import { cn } from '@/lib/utils'
import { footerLabel, statusBadge } from '@/lib/live'
import { useOpenFilm } from '@/movies/filmParam'
import { Poster } from '@/movies/Poster'

export function LiveMovieCard({ film, size = 'large', eager = false }: {
  film: LiveMovie; size?: 'large' | 'small'; eager?: boolean
}) {
  const open = useOpenFilm()
  const body = (
    <>
      <span className="relative block">
        <Poster poster={film.poster} title={film.title} eager={eager} />
        <span className={cn('bg-background/90 text-foreground absolute top-1.5 left-1.5 rounded px-1.5 py-0.5 text-xs font-medium shadow-xs',
          size === 'small' && film.status === 'upcoming' && 'text-sm font-semibold')}>
          <time dateTime={film.release_date}>{statusBadge(film)}</time>
        </span>
      </span>
      <span className="grid gap-0.5">
        <span className="line-clamp-2 text-sm font-medium leading-tight group-hover:underline">{film.title}</span>
        <span className="text-muted-foreground text-xs">{footerLabel(film)}</span>
      </span>
    </>
  )
  const className = 'group grid content-start gap-2 rounded-md text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring'
  return film.movie_id != null ? (
    <Link to={`/movies/${film.movie_id}`} data-testid="live-card" className={className}>{body}</Link>
  ) : (
    <button type="button" data-testid="live-card" aria-haspopup="dialog" onClick={() => open(film.tmdb_id)} className={className}>
      {body}
    </button>
  )
}
