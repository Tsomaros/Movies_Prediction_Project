// "New & upcoming matches" (V1.2): up to 3 live films whose title matches a search, above the results on /browse
// (and in place of "No movies match" when the database has none). They come with the search answer itself, from
// the server's cache, so showing them costs no extra request.
import type { LiveMovie } from '@/api/client'
import { LiveMovieCard } from '@/movies/LiveMovieCard'

export function LiveMatches({ films }: { films: LiveMovie[] }) {
  if (films.length === 0) return null
  return (
    <section aria-label="New & upcoming matches" data-testid="live-matches" className="grid gap-2">
      <h2 className="text-sm font-medium">New &amp; upcoming matches</h2>
      <ul className="flex gap-3">
        {films.map(film => <li key={film.tmdb_id} className="w-28 shrink-0"><LiveMovieCard film={film} size="small" /></li>)}
      </ul>
    </section>
  )
}
