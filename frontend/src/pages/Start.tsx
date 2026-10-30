// /: the start page, with no header or footer (its route is `bare`). The title, then two bordered cards in
// the middle of the screen, each one link over a poster collage (scripts/build_collages.py): Movies opens
// /movies, Series opens /series ("coming soon"). Side by side from `sm`, stacked on a phone. Hovering or
// focusing a card lifts it, lightens its overlay and lifts its title. The collage pans slowly, unless the
// visitor prefers reduced motion (then `data-pan="off"`). Below: Predict, About, the theme and TMDB's notice.
import { ClapperboardIcon } from 'lucide-react'
import { Link } from 'react-router'

import { TmdbNotice } from '@/app/Layout'
import { ThemeToggle } from '@/app/theme'
import { cn } from '@/lib/utils'
import { useReducedMotion } from '@/lib/useReducedMotion'

const CARDS = [
  { to: '/movies', title: 'Movies', text: 'Browse 80,000 films from 1960 to 2026, and plan your own.', image: '/collages/movies.webp' },
  { to: '/series', title: 'Series', text: 'Coming soon.', image: '/collages/series.webp' },
] as const

function Card({ card, still }: { card: (typeof CARDS)[number]; still: boolean }) {
  return (
    <Link to={card.to} data-testid={`panel-${card.title.toLowerCase()}`} data-pan={still ? 'off' : 'on'}
      className={cn('group relative isolate flex aspect-[16/10] w-full max-w-[24rem] sm:aspect-[4/5] items-end overflow-hidden rounded-xl border bg-neutral-900 shadow-md outline-none sm:w-80',
        'transition-[translate,box-shadow] duration-300 ease-out hover:-translate-y-1 hover:shadow-xl focus-visible:-translate-y-1 focus-visible:shadow-xl',
        'focus-visible:ring-primary focus-visible:ring-4 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        'focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-solid focus-visible:outline-white')}>
      <img src={card.image} alt="" width={1200} height={1000} fetchPriority="high"
        className={cn('absolute -inset-[6%] -z-10 size-[112%] max-w-none object-cover', !still && 'animate-pan motion-reduce:animate-none')} />
      <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-t from-black/85 via-black/50 to-black/30 transition-opacity duration-300 group-hover:opacity-75 group-focus-visible:opacity-75" />
      <div className="p-5 text-white transition-transform duration-300 group-hover:-translate-y-1.5 group-focus-visible:-translate-y-1.5">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">{card.title}</h2>
        <p className="mt-1 text-sm text-white/85 sm:text-base">{card.text}</p>
      </div>
    </Link>
  )
}

export default function Start() {
  const still = useReducedMotion()
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 px-4 py-8 sm:gap-8 sm:py-10">
      <title>Movie Prediction</title>
      <div className="grid justify-items-center gap-2 text-center">
        <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          <ClapperboardIcon className="text-primary size-7 sm:size-8" aria-hidden /> Movie Prediction
        </h1>
        <p className="text-muted-foreground">How might your film do? Start with the films, or the series to come.</p>
      </div>
      <div className="flex w-full flex-col items-center gap-6 sm:w-auto sm:flex-row">
        {CARDS.map(c => <Card key={c.to} card={c} still={still} />)}
      </div>
      <div className="grid justify-items-center gap-4">
        <nav aria-label="More" className="flex items-center gap-1 text-sm">
          <Link to="/predict" className="text-muted-foreground hover:text-foreground rounded-md px-3 py-1.5 hover:bg-accent">Predict a film</Link>
          <span aria-hidden className="text-muted-foreground">·</span>
          <Link to="/about" className="text-muted-foreground hover:text-foreground rounded-md px-3 py-1.5 hover:bg-accent">About</Link>
          <ThemeToggle />
        </nav>
        <TmdbNotice className="text-muted-foreground flex-col text-center text-xs sm:flex-row sm:text-left" />
      </div>
    </main>
  )
}
