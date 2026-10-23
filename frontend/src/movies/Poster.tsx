// A film's poster at a fixed 2:3, so a grid never jumps while images load: the small (w342) or large (w780)
// TMDB image, loaded lazily, or a designed placeholder with the title when TMDB has none.
import { FilmIcon } from 'lucide-react'

import type { MovieSummary } from '@/api/client'
import { cn } from '@/lib/utils'

export function Poster({ poster, title, size = 'small', eager = false, className }: {
  poster: MovieSummary['poster']; title: string; size?: 'small' | 'large'; eager?: boolean; className?: string
}) {
  return (
    <div className={cn('bg-muted aspect-[2/3] w-full overflow-hidden rounded-md', className)}>
      {poster ? (
        <img src={poster[size]} alt={`Poster of ${title}`} loading={eager ? 'eager' : 'lazy'} decoding="async"
          className="size-full object-cover" />
      ) : (
        <div role="img" aria-label={`No poster for ${title}`}
          className="text-muted-foreground flex size-full flex-col items-center justify-center gap-2 bg-gradient-to-b from-muted to-accent/60 p-3 text-center">
          <FilmIcon className="size-7 opacity-60" aria-hidden />
          <span className="line-clamp-3 text-xs font-medium">{title}</span>
        </div>
      )}
    </div>
  )
}
