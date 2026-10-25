// "View as table": every dated film of the Career chart as a plain table (oldest first, like the chart), for
// screen readers and for anyone who wants the numbers: the score, the box office (trusted 2025 $, else "—") and
// the votes. Acting adds the character and lead or supporting.
import { Link } from 'react-router'

import type { CareerFilm } from '@/api/client'
import { money, points } from '@/result/format'

export function CareerTable({ films }: { films: CareerFilm[] }) {
  const acting = films.some(f => f.lead !== null)
  return (
    <div className="overflow-x-auto">
      <table aria-label="Career films" className="w-full text-sm">
        <thead>
          <tr className="text-muted-foreground border-b text-left text-xs">
            <th scope="col" className="py-1 pr-3 font-medium">Year</th>
            <th scope="col" className="py-1 pr-3 font-medium">Title</th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">Score</th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">Box office</th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">Votes</th>
            {acting && <th scope="col" className="py-1 font-medium">Role</th>}
          </tr>
        </thead>
        <tbody>
          {films.map(f => (
            <tr key={f.movie_id} className="border-b last:border-0">
              <td className="py-1 pr-3 tabular-nums">{f.year}</td>
              <td className="py-1 pr-3"><Link to={`/movies/${f.movie_id}`} className="underline">{f.title}</Link></td>
              <td className={`py-1 pr-3 text-right tabular-nums ${f.rated ? '' : 'text-muted-foreground'}`}>
                {f.score === null ? '–' : points(f.score)}
              </td>
              <td className="py-1 pr-3 text-right tabular-nums">{f.revenue === null ? '—' : money(f.revenue)}</td>
              <td className="py-1 pr-3 text-right tabular-nums">{f.vote_count.toLocaleString('en-US')}</td>
              {acting && (
                <td className="py-1">
                  {[f.character && `as ${f.character}`, f.lead === null ? null : f.lead ? 'lead' : 'supporting'].filter(Boolean).join(' · ')}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
