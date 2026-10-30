// A role's films as a poster grid; logged in, with list badges and quick buttons (one status request per 48 films).
import { useMe } from '@/auth/session'
import { cn } from '@/lib/utils'
import { useStatuses } from '@/me/hooks'
import { GRID } from '@/movies/browse'
import { MovieCard } from '@/movies/MovieCard'

import type { Role } from './roles'

export function FilmGrid({ films, writing }: { films: Role['films']; writing: boolean }) {
  const { user } = useMe()
  const statuses = useStatuses(user ? films.map(f => f.id) : [])
  return (
    <ul className={cn('grid gap-4', GRID.medium)} aria-label="Films">
      {films.map((f, i) => (
        <li key={f.id}><MovieCard film={f} eager={i < 4} entry={statuses.get(f.id)} quick={user !== null}
          subtitle={f.character ? `as ${f.character}` : writing ? f.jobs.join(', ') : undefined} /></li>
      ))}
    </ul>
  )
}
