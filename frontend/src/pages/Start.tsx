// /: the start page. Two panels, each one link over a poster collage (scripts/build_collages.py): Movies opens
// /movies, Series opens /series ("coming soon"). Side by side from `sm`, stacked on a phone. Hovering or
// focusing a panel widens it to about 58% (grow 1.38 against 1), lightens its overlay and lifts its title.
// The collage pans slowly, unless the visitor prefers reduced motion (then `data-pan="off"`).
import { Link } from 'react-router'

import { cn } from '@/lib/utils'
import { useReducedMotion } from '@/lib/useReducedMotion'

const PANELS = [
  { to: '/movies', title: 'Movies', text: 'Browse 79,000 films from 1960 to 2025, and plan your own.', image: '/collages/movies.webp' },
  { to: '/series', title: 'Series', text: 'Coming soon.', image: '/collages/series.webp' },
] as const

function Panel({ panel, still }: { panel: (typeof PANELS)[number]; still: boolean }) {
  return (
    <Link to={panel.to} data-testid={`panel-${panel.title.toLowerCase()}`} data-pan={still ? 'off' : 'on'}
      className={cn('group relative isolate flex min-h-[45svh] basis-0 grow items-end overflow-hidden bg-neutral-900 outline-none',
        'transition-[flex-grow] duration-500 ease-out sm:min-h-0 sm:hover:grow-[1.38] sm:focus-visible:grow-[1.38]',
        'focus-visible:outline-4 focus-visible:-outline-offset-4 focus-visible:outline-solid focus-visible:outline-white')}>
      <img src={panel.image} alt="" width={1200} height={1000} fetchPriority="high"
        className={cn('absolute -inset-[6%] -z-10 size-[112%] max-w-none object-cover', !still && 'animate-pan motion-reduce:animate-none')} />
      <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-t from-black/85 via-black/55 to-black/40 transition-opacity duration-500 group-hover:opacity-75 group-focus-visible:opacity-75" />
      <div className="p-6 text-white transition-transform duration-500 group-hover:-translate-y-2 group-focus-visible:-translate-y-2 sm:p-10">
        <h2 className="text-4xl font-semibold tracking-tight sm:text-6xl">{panel.title}</h2>
        <p className="mt-2 text-base text-white/85 sm:text-lg">{panel.text}</p>
      </div>
    </Link>
  )
}

export default function Start() {
  const still = useReducedMotion()
  return (
    <section className="flex flex-1 flex-col sm:min-h-[calc(100svh-8rem)] sm:flex-row">
      <title>Movie Prediction</title>
      <h1 className="sr-only">Movie Prediction</h1>
      {PANELS.map(p => <Panel key={p.to} panel={p} still={still} />)}
    </section>
  )
}
