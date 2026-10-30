// A sideways-scrolling row of live films (V1.2): a heading, "See all", up to ROW_MAX cards that snap as they scroll
// (swipe on a phone, arrow buttons from `md`). `variant` small is the narrower "Coming soon" strip.
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { useId, useRef } from 'react'
import { Link } from 'react-router'

import type { LiveMovie } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { LiveMovieCard } from '@/movies/LiveMovieCard'

export const ROW_MAX = 20
const HEIGHT = 'h-[17rem]' // the row's height while loading, so nothing jumps when it fills

export function LiveRowSkeleton() {
  return <div data-testid="live-row-skeleton" aria-hidden className={cn('grid gap-3', HEIGHT)}><Skeleton className="h-full" /></div>
}

export function LiveRow({ title, films, seeAllHref, variant = 'large', first = false }: {
  title: string; films: LiveMovie[]; seeAllHref: string; variant?: 'large' | 'small'; first?: boolean
}) {
  const headingId = useId()
  const scroller = useRef<HTMLUListElement>(null)
  const scroll = (dir: 1 | -1) => scroller.current?.scrollBy({ left: dir * scroller.current.clientWidth * 0.8, behavior: 'smooth' })
  const arrow = 'bg-background/90 absolute top-1/3 z-10 hidden size-9 items-center justify-center rounded-full border shadow-sm hover:bg-accent md:inline-flex'
  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id={headingId} className="text-lg font-semibold">{title}</h2>
        <Link to={seeAllHref} className="text-primary inline-flex items-center text-sm hover:underline">
          See all<span className="sr-only"> {title}</span><ChevronRightIcon className="size-4" aria-hidden />
        </Link>
      </div>
      <div className="relative">
        <button type="button" aria-label={`Scroll ${title} left`} onClick={() => scroll(-1)} className={cn(arrow, '-left-3')}>
          <ChevronLeftIcon className="size-5" aria-hidden />
        </button>
        <ul ref={scroller} className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
          {films.slice(0, ROW_MAX).map((film, i) => (
            <li key={film.tmdb_id} className={cn('shrink-0 snap-start', variant === 'large' ? 'w-32 sm:w-36' : 'w-24 sm:w-28')}>
              <LiveMovieCard film={film} size={variant} eager={first && i < 6} />
            </li>
          ))}
        </ul>
        <button type="button" aria-label={`Scroll ${title} right`} onClick={() => scroll(1)} className={cn(arrow, '-right-3')}>
          <ChevronRightIcon className="size-5" aria-hidden />
        </button>
      </div>
    </section>
  )
}
