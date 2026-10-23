// Five earlier films like the planned one, with what they really cost, earned and scored. Each links to its
// film page; its "why" tags come from the API (the parts of the similarity that matched).
import { FilmIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { Comparable } from '@/api/client'
import { money, points } from '@/result/format'

function Poster({ film }: { film: Comparable }) {
  return (
    <div className="bg-muted aspect-[2/3] w-full overflow-hidden rounded-md">
      {film.poster ? (
        <img src={film.poster.small} alt={`Poster of ${film.title}`} loading="lazy" decoding="async"
          className="size-full object-cover" />
      ) : (
        <div className="text-muted-foreground flex size-full flex-col items-center justify-center gap-1 p-2 text-center text-xs">
          <FilmIcon className="size-6" aria-hidden />
          No poster
        </div>
      )}
    </div>
  )
}

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
          {films.map(film => (
            <li key={film.id} className="grid content-start gap-2">
              <Link to={`/movies/${film.id}`} className="group grid gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-ring">
                <Poster film={film} />
                <span className="font-medium leading-tight group-hover:underline">
                  {film.title} <span className="text-muted-foreground font-normal">({film.year})</span>
                </span>
              </Link>
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
          ))}
        </ul>
      )}
    </section>
  )
}
