// The film page's "Made by" list: key crew by job (names link to person pages), studios, countries, franchise.
import { Link } from 'react-router'

import type { MovieDetail as Film } from '@/api/client'
import { codeName } from '@/form/format'
import { crewByJob } from '@/movies/people'

const CREW_JOBS = ['Director', 'Screenplay', 'Writer', 'Producer', 'Original Music Composer', 'Director of Photography', 'Editor']
const JOB_LABELS: Record<string, string> = { 'Original Music Composer': 'Music', 'Director of Photography': 'Cinematography' }
const MAX_PER_JOB = 4

export function MadeBy({ film: f }: { film: Film }) {
  const crew = crewByJob(f.crew, CREW_JOBS)
  return (
    <section aria-labelledby="made-heading" className="grid content-start gap-2 text-sm">
      <h2 id="made-heading" className="text-lg font-semibold">Made by</h2>
      <dl className="grid gap-1.5 sm:grid-cols-[9rem_1fr]">
        {crew.map(g => (
          <div key={g.job} className="contents">
            <dt className="text-muted-foreground">{JOB_LABELS[g.job] ?? g.job}</dt>
            <dd>
              {g.people.slice(0, MAX_PER_JOB).map((p, i) => (
                <span key={p.id}>{i > 0 && ', '}<Link to={`/people/${p.id}`} className="hover:underline">{p.name}</Link></span>
              ))}
              {g.people.length > MAX_PER_JOB && ` and ${g.people.length - MAX_PER_JOB} more`}
            </dd>
          </div>
        ))}
        {f.companies.length > 0 && <><dt className="text-muted-foreground">Studios</dt><dd>{f.companies.map(c => c.name).join(', ')}</dd></>}
        {f.countries.length > 0 && <><dt className="text-muted-foreground">Countries</dt><dd>{f.countries.map(c => codeName('region', c)).join(', ')}</dd></>}
        {f.franchise && <><dt className="text-muted-foreground">Franchise</dt><dd>{f.franchise.name}</dd></>}
      </dl>
    </section>
  )
}
