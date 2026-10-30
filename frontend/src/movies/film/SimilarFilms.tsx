// The film page's Similar films grid; logged in, each film shows its list badge and quick buttons.
import { Link } from 'react-router'

import type { MovieDetail as Film } from '@/api/client'
import { useMe } from '@/auth/session'
import { QuickButtons, StatusBadge } from '@/me/CardStatus'
import { useStatuses } from '@/me/hooks'
import { Poster } from '@/movies/Poster'
import { points } from '@/result/format'

export function SimilarFilms({ films }: { films: Film['similar'] }) {
  const { user } = useMe()
  const statuses = useStatuses(user ? films.map(s => s.id) : [])
  if (films.length === 0) return null
  return (
    <section aria-labelledby="similar-heading" className="grid gap-3">
      <h2 id="similar-heading" className="text-lg font-semibold">Similar films</h2>
      <ul className="grid grid-cols-3 gap-4 sm:grid-cols-6">
        {films.map(s => { const entry = statuses.get(s.id); return (
          <li key={s.id} className="group/card relative">
            <Link to={`/movies/${s.id}`} className="group grid gap-1.5 rounded-md focus-visible:outline-2 focus-visible:outline-ring">
              <span className="relative block">
                <Poster poster={s.poster} title={s.title} />
                {entry && <StatusBadge entry={entry} />}
              </span>
              <span className="text-sm leading-tight group-hover:underline">{s.title}</span>
              <span className="text-muted-foreground text-xs">{s.year} · {points(s.score)}</span>
              {s.why[0] && <span className="text-muted-foreground text-[11px]">{s.why[0]}</span>}
            </Link>
            {user && <QuickButtons movieId={s.id} title={s.title} entry={entry} />}
          </li>
        )})}
      </ul>
    </section>
  )
}
