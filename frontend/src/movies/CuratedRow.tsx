// One curated row on /movies: a heading, "See all" (the same query on /browse) and up to ROW_SIZE posters
// that scroll sideways on a phone and wrap into a grid on wider screens. Logged in, one status request per row
// gives the cards their badges and quick list buttons.
import { ChevronRightIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { useMovies } from '@/api/hooks'
import { useMe } from '@/auth/session'
import { Skeleton } from '@/components/ui/skeleton'
import { useStatuses } from '@/me/hooks'
import { browseLink, EMPTY, toQuery } from '@/movies/browse'
import { MovieCard } from '@/movies/MovieCard'
import { ROW_SIZE, type CuratedRow as Row } from '@/movies/rows'

/** `first`: the top row, whose posters load at once (the page's largest paint). `header`: something beside the title
 *  (the New arrivals switch); `emptyText`: what to say when the query finds no film. */
export function CuratedRow({ row, first = false, header, emptyText }: {
  row: Row; first?: boolean; header?: ReactNode; emptyText?: string
}) {
  const movies = useMovies({ ...toQuery({ ...EMPTY, ...row.filters }), page_size: ROW_SIZE })
  const { user } = useMe()
  const statuses = useStatuses(user && movies.data ? movies.data.items.map(f => f.id) : [])
  const headingId = `row-${row.key}-heading`
  return (
    <section aria-labelledby={headingId} data-testid={`row-${row.key}`} className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <h2 id={headingId} className="text-lg font-semibold">{row.title}</h2>
        {header}
        <Link to={browseLink(row.filters)} className="text-primary inline-flex items-center text-sm hover:underline">
          See all <span className="sr-only">: {row.title}</span><ChevronRightIcon className="size-4" aria-hidden />
        </Link>
      </div>
      {movies.isError ? (
        <p className="text-muted-foreground text-sm">This row couldn't load right now.</p>
      ) : emptyText && movies.data?.items.length === 0 ? (
        <p className="text-muted-foreground text-sm">{emptyText}</p>
      ) : (
        <ul className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-6 sm:overflow-visible sm:px-0">
          {(movies.data?.items ?? Array.from({ length: 6 }, () => null)).map((film, i) => (
            <li key={film?.id ?? `skeleton-${i}`} className="w-28 shrink-0 snap-start sm:w-auto [&:nth-child(n+7)]:sm:hidden">
              {film ? <MovieCard film={film} showRevenue={row.showRevenue} eager={first && i < 6}
                entry={statuses.get(film.id)} quick={user !== null} /> : <Skeleton className="aspect-[2/3]" />}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
