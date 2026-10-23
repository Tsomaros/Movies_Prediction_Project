// One curated row on the home page: a heading, "See all" (the same query on /movies) and up to ROW_SIZE posters
// that scroll sideways on a phone and wrap into a grid on wider screens.
import { ChevronRightIcon } from 'lucide-react'
import { Link } from 'react-router'

import { useMovies } from '@/api/hooks'
import { Skeleton } from '@/components/ui/skeleton'
import { browseLink, EMPTY, toQuery } from '@/movies/browse'
import { MovieCard } from '@/movies/MovieCard'
import { ROW_SIZE, type CuratedRow as Row } from '@/movies/rows'

export function CuratedRow({ row }: { row: Row }) {
  const movies = useMovies({ ...toQuery({ ...EMPTY, ...row.filters }), page_size: ROW_SIZE })
  const headingId = `row-${row.key}-heading`
  return (
    <section aria-labelledby={headingId} data-testid={`row-${row.key}`} className="grid gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id={headingId} className="text-lg font-semibold">{row.title}</h2>
        <Link to={browseLink(row.filters)} className="text-primary inline-flex items-center text-sm hover:underline">
          See all <span className="sr-only">: {row.title}</span><ChevronRightIcon className="size-4" aria-hidden />
        </Link>
      </div>
      {movies.isError ? (
        <p className="text-muted-foreground text-sm">This row couldn't load right now.</p>
      ) : (
        <ul className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-6 sm:overflow-visible sm:px-0">
          {(movies.data?.items ?? Array.from({ length: 6 }, () => null)).map((film, i) => (
            <li key={film?.id ?? `skeleton-${i}`} className="w-28 shrink-0 snap-start sm:w-auto [&:nth-child(n+7)]:sm:hidden">
              {film ? <MovieCard film={film} showRevenue={row.showRevenue} /> : <Skeleton className="aspect-[2/3]" />}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
