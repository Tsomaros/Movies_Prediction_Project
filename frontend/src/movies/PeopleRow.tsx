// The people row above browse search's films (Day 14.6): up to PEOPLE_ROW actors whose name matches the search
// (from 2 characters, the same debounced ?q= as the films), each a link to their page with a TMDB photo or an
// initials avatar, the name and the film they're known for. It scrolls sideways (with snap) on a narrow screen.
import { Link } from 'react-router'

import type { PersonMatch } from '@/api/client'
import { initials, nameHue } from '@/movies/people'

export const PEOPLE_ROW = 6

export function PeopleRow({ people }: { people: PersonMatch[] }) {
  if (people.length === 0) return null
  return (
    <section aria-labelledby="people-heading" className="grid gap-2" data-testid="people-row">
      <h2 id="people-heading" className="text-sm font-semibold">People</h2>
      <ul className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-1">
        {people.map(p => (
          <li key={p.id} className="w-28 shrink-0 snap-start">
            <Link to={`/people/${p.id}`} data-testid="person-card"
              className="group grid justify-items-center gap-1 rounded-md p-1 text-center focus-visible:outline-2 focus-visible:outline-ring">
              {p.thumb ? (
                <img src={p.thumb} alt="" loading="lazy" decoding="async" className="bg-muted size-20 rounded-full object-cover" />
              ) : (
                <span aria-hidden className="inline-flex size-20 items-center justify-center rounded-full text-lg font-semibold text-white"
                  style={{ backgroundColor: `hsl(${nameHue(p.name)} 45% 38%)` }}>
                  {initials(p.name)}
                </span>
              )}
              <span className="line-clamp-2 text-sm font-medium leading-tight group-hover:underline">{p.name}</span>
              {p.known_for && <span className="text-muted-foreground line-clamp-1 text-xs">{p.known_for}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
