// Five earlier films like the planned one, with what they really cost, earned and scored. Each links to its
// film page; its "why" tags come from the API (the parts of the similarity that matched). Logged in, the posters
// carry the list badge and quick list buttons.
import { Link } from 'react-router'

import type { Comparable } from '@/api/client'
import { useMe } from '@/auth/session'
import { QuickButtons, StatusBadge } from '@/me/CardStatus'
import { useStatuses } from '@/me/hooks'
import { Poster } from '@/movies/Poster'
import { money, points } from '@/result/format'

function Fact({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={value === null ? 'text-muted-foreground italic' : 'tabular-nums'}>
        {value === null ? 'not reported' : money(value)}
      </dd>
    </div>
  )
}

export function Comparables({ films }: { films: Comparable[] }) {
  const { user } = useMe()
  const statuses = useStatuses(user ? films.map(f => f.id) : [])
  return (
    <section aria-labelledby="comparables-heading" className="bg-card grid gap-3 rounded-lg border p-4 sm:p-6">
      <div>
        <h2 id="comparables-heading" className="text-lg font-semibold">Films like yours</h2>
        <p className="text-muted-foreground text-sm">
          Earlier films most similar to your plan, with their real figures (2025 dollars). Only films released
          before your date count.
        </p>
      </div>
      {films.length === 0 ? (
        <p className="text-muted-foreground text-sm">No earlier film is close enough to show.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {films.map(film => { const entry = statuses.get(film.id); return (
            <li key={film.id} className="grid content-start gap-2">
              <div className="group/card relative">
                <Link to={`/movies/${film.id}`} className="group grid gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-ring">
                  <span className="relative block">
                    <Poster poster={film.poster} title={film.title} />
                    {entry && <StatusBadge entry={entry} />}
                  </span>
                  <span className="font-medium leading-tight group-hover:underline">
                    {film.title} <span className="text-muted-foreground font-normal">({film.year})</span>
                  </span>
                </Link>
                {user && <QuickButtons movieId={film.id} title={film.title} entry={entry} />}
              </div>
              <dl className="grid gap-0.5 text-xs">
                <Fact label="Budget" value={film.budget ?? null} />
                <Fact label="Revenue" value={film.revenue ?? null} />
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Score</dt>
                  <dd className="tabular-nums">{points(film.score)}</dd>
                </div>
              </dl>
              {film.why.length > 0 && (
                <ul aria-label="Why similar" className="flex flex-wrap gap-1">
                  {film.why.map(w => (
                    <li key={w} className="bg-secondary text-secondary-foreground rounded-full px-2 py-0.5 text-[11px] leading-4">{w}</li>
                  ))}
                </ul>
              )}
            </li>
          )})}
        </ul>
      )}
    </section>
  )
}
