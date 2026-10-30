// The film page's Cast section: photo (or initials), name linked to the person page, character.
import { Link } from 'react-router'

import type { MovieDetail as Film } from '@/api/client'
import { initials, nameHue } from '@/movies/people'

function Avatar({ name, photo }: { name: string; photo?: Film['cast'][number]['photo'] }) {
  if (photo) return <img src={photo.small} alt="" loading="lazy" decoding="async" className="bg-muted size-12 shrink-0 rounded-full object-cover" />
  return (
    <span aria-hidden className="inline-flex size-12 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
      style={{ backgroundColor: `hsl(${nameHue(name)} 45% 38%)` }}>
      {initials(name)}
    </span>
  )
}

export function CastList({ cast }: { cast: Film['cast'] }) {
  if (cast.length === 0) return null
  return (
    <section aria-labelledby="cast-heading" className="grid gap-3">
      <h2 id="cast-heading" className="text-lg font-semibold">Cast</h2>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cast.map(c => (
          <li key={`${c.id}-${c.order}`} className="flex items-center gap-3">
            <Avatar name={c.name ?? '?'} photo={c.photo} />
            <span className="grid">
              {c.linked === false ? <span className="font-medium">{c.name}</span>
                : <Link to={`/people/${c.id}`} className="font-medium hover:underline">{c.name}</Link>}
              {c.character && <span className="text-muted-foreground text-sm">{c.character}</span>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
