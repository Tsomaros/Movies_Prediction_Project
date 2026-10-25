// /people/:id: one person (Day 14.6). TMDB's photo, life dates, birthplace and biography when the person pull
// found them (otherwise an initials avatar), a stats strip from our own data, their films as a poster grid with
// the character they played (sorted by ?sort=, newest first by default), their key crew credits, and "Predict a
// film with this actor" (a fresh form with them as the lead). The biography is plain text: blank lines make
// paragraphs, nothing is read as HTML.
import { ArrowLeftIcon, ExternalLinkIcon, SparklesIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError, type PersonDetail } from '@/api/client'
import { usePerson } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { encodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { cn } from '@/lib/utils'
import { GRID } from '@/movies/browse'
import { FilterSelect } from '@/movies/Filters'
import { MovieCard } from '@/movies/MovieCard'
import { FILM_SORTS, formatLife, initials, nameHue, readFilmSort, sortFilms } from '@/movies/people'
import { personToForm } from '@/movies/predictLike'
import { money, points } from '@/result/format'

const CREW_LABELS: Record<string, string> = {
  Director: 'directed', Screenplay: 'wrote', Writer: 'wrote', Producer: 'produced', 'Original Music Composer': 'scored',
  'Director of Photography': 'shot', Editor: 'edited',
}
const LONG_BIO = 600 // characters: longer biographies start clamped to 4 lines, with "Read more"

function Avatar({ name }: { name: string }) {
  return (
    <span aria-hidden className="flex aspect-[2/3] w-full items-center justify-center rounded-md text-4xl font-semibold text-white"
      style={{ backgroundColor: `hsl(${nameHue(name)} 45% 38%)` }}>
      {initials(name)}
    </span>
  )
}

function Biography({ text }: { text: string }) {
  const long = text.length > LONG_BIO
  const [open, setOpen] = useState(!long)
  const paragraphs = text.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
  return (
    <div className="grid justify-items-start gap-1">
      <div className={cn('grid max-w-prose gap-2', !open && 'line-clamp-4')} data-testid="biography">
        {paragraphs.map((p, i) => <p key={i}>{p}</p>)}
      </div>
      {long && (
        <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} className="text-primary text-sm underline">
          {open ? 'Show less' : 'Read more'}
        </button>
      )}
    </div>
  )
}

function Stats({ person }: { person: PersonDetail }) {
  const s = person.stats
  const chips: { key: string; content: ReactNode }[] = []
  if (s.film_count > 0) {
    const years = s.first_year == null ? '' : s.first_year === s.last_year ? ` · ${s.first_year}` : ` · ${s.first_year}–${s.last_year}`
    chips.push({ key: 'films', content: `${s.film_count} ${s.film_count === 1 ? 'film' : 'films'}${years}` })
  }
  if (s.top_genres.length > 0) chips.push({ key: 'genres', content: `Mostly ${s.top_genres.map(g => g.name).join(', ')}` })
  if (s.avg_score) chips.push({ key: 'score', content: `Average score ${points(s.avg_score.value)} from ${s.avg_score.films} ${s.avg_score.films === 1 ? 'film' : 'films'}` })
  if (s.box_office_2025) {
    const b = s.box_office_2025
    chips.push({ key: 'money', content: `${money(b.total)} box office (2025 $) from ${b.films} of ${b.of} films` })
  }
  for (const [key, label, ref] of [['costar', 'Most often with', s.top_costar], ['director', 'Most often directed by', s.top_director]] as const) {
    if (ref) chips.push({ key, content: <>{label} <Link to={`/people/${ref.id}`} className="font-medium underline">{ref.name}</Link> ({ref.shared_films} films)</> })
  }
  if (chips.length === 0) return null
  return (
    <ul aria-label="Stats" className="flex flex-wrap gap-2">
      {chips.map(c => <li key={c.key} className="bg-secondary text-secondary-foreground rounded-full px-3 py-1 text-sm">{c.content}</li>)}
    </ul>
  )
}

function CrewCredits({ person }: { person: PersonDetail }) {
  const groups = new Map<string, PersonDetail['crew_credits'][string]>() // "wrote" gathers Screenplay and Writer
  for (const [job, films] of Object.entries(person.crew_credits)) {
    const label = CREW_LABELS[job] ?? job.toLowerCase()
    const seen = new Set((groups.get(label) ?? []).map(f => f.id))
    groups.set(label, [...(groups.get(label) ?? []), ...films.filter(f => !seen.has(f.id))])
  }
  if (groups.size === 0) return null
  const also = person.cast_credits.length > 0 ? 'Also ' : ''
  return (
    <section aria-labelledby="crew-heading" className="grid gap-3">
      <h2 id="crew-heading" className="sr-only">Behind the camera</h2>
      {[...groups].map(([label, films]) => (
        <div key={label} className="grid gap-1">
          <h3 className="font-semibold">{also ? `${also}${label}` : label[0].toUpperCase() + label.slice(1)}</h3>
          <ul className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
            {films.map(f => (
              <li key={f.id}><Link to={`/movies/${f.id}`} className="hover:underline">{f.title}</Link>
                {f.year && <span className="text-muted-foreground"> ({f.year})</span>}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}

function Loading() {
  return (
    <div className="grid gap-6 sm:grid-cols-[12rem_1fr]" aria-busy="true">
      <span className="sr-only">Loading…</span>
      <Skeleton className="aspect-[2/3]" />
      <div className="grid content-start gap-3"><Skeleton className="h-9 w-2/3" /><Skeleton className="h-5 w-1/2" /><Skeleton className="h-24" /></div>
    </div>
  )
}

export function NotFoundPerson() {
  return (
    <div className="grid justify-items-start gap-4">
      <title>Person not found · Movie Prediction</title>
      <h1 className="text-2xl font-semibold">We don't have this person</h1>
      <p className="text-muted-foreground">The link may be wrong, or they aren't in our TMDB data.</p>
      <div className="flex gap-2">
        <Button asChild><Link to="/browse">Search films and people</Link></Button>
        <Button asChild variant="outline"><Link to="/">Start page</Link></Button>
      </div>
    </div>
  )
}

export default function Person() {
  const { id } = useParams()
  const personId = id && /^\d+$/.test(id) ? Number(id) : null
  const person = usePerson(personId)
  const [params, setParams] = useSearchParams()
  const sort = readFilmSort(params.get('sort'))
  const navigate = useNavigate()

  if (personId === null || (person.error instanceof ApiError && person.error.kind === 'not_found')) return <NotFoundPerson />
  if (person.isError) {
    return (
      <div role="alert" className="grid justify-items-start gap-3">
        <p>This page couldn't load: {person.error.message}</p>
        <Button variant="outline" onClick={() => person.refetch()}>Try again</Button>
      </div>
    )
  }
  if (!person.data) return <><SlowNotice pending /><Loading /></>

  const p = person.data
  const name = p.name ?? 'Unknown'
  const life = formatLife(p.birthday, p.deathday)
  const films = sortFilms(p.cast_credits, sort)
  const predict = () => navigate(`/predict?${new URLSearchParams({ [URL_PARAM]: encodeForm(personToForm({ id: p.id, name })), [LIKE_PARAM]: name })}`)
  const links = [
    p.imdb_url && { href: p.imdb_url, label: 'IMDb' }, p.homepage && { href: p.homepage, label: 'Website' },
    { href: p.tmdb_url, label: 'TMDB' },
  ].filter(Boolean) as { href: string; label: string }[]

  return (
    <article className="grid gap-8">
      <title>{`${name} · Movie Prediction`}</title>
      <Link to="/browse" className="text-muted-foreground inline-flex w-fit items-center gap-1 text-sm hover:underline">
        <ArrowLeftIcon className="size-4" aria-hidden /> Browse films
      </Link>

      <div className="grid gap-6 sm:grid-cols-[12rem_1fr]">
        <div className="mx-auto w-40 sm:w-full">
          {p.photo ? (
            <div className="bg-muted aspect-[2/3] overflow-hidden rounded-md">
              <img src={p.photo.large} alt={`Photo of ${name}`} loading="eager" decoding="async" className="size-full object-cover" />
            </div>
          ) : <Avatar name={name} />}
        </div>
        <div className="grid content-start gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{name}</h1>
            {p.known_for_department && <p className="text-muted-foreground text-sm">{p.known_for_department}</p>}
          </div>
          {(life || p.place_of_birth) && <p className="text-sm">{[life, p.place_of_birth].filter(Boolean).join(' · ')}</p>}
          <Stats person={p} />
          {p.biography && <Biography text={p.biography} />}
          <ul aria-label="Elsewhere" className="flex flex-wrap gap-3 text-sm">
            {links.map(l => (
              <li key={l.label}>
                <a href={l.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline">
                  {l.label} <ExternalLinkIcon className="size-3" aria-hidden />
                </a>
              </li>
            ))}
          </ul>
          {p.cast_credits.length > 0 && (
            <div>
              <Button onClick={predict}><SparklesIcon /> Predict a film with this actor</Button>
              <p className="text-muted-foreground mt-1 text-xs">Opens the form with {name} as the lead; you fill in the rest.</p>
            </div>
          )}
        </div>
      </div>

      {p.cast_credits.length > 0 && (
        <section aria-labelledby="films-heading" className="grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="films-heading" className="text-lg font-semibold">Films</h2>
            <FilterSelect label="Sort films" value={sort} className="bg-card h-8 w-44" choices={FILM_SORTS}
              onChange={s => setParams(s && s !== 'newest' ? { sort: s } : {}, { replace: true, preventScrollReset: true })} />
          </div>
          <ul className={cn('grid gap-4', GRID.medium)} aria-label="Films">
            {films.map((f, i) => (
              <li key={f.id}><MovieCard film={f} eager={i < 4} subtitle={f.character ? `as ${f.character}` : undefined} /></li>
            ))}
          </ul>
        </section>
      )}

      <CrewCredits person={p} />

      <p className="text-muted-foreground border-t pt-4 text-xs">
        Data from TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.
      </p>
    </article>
  )
}
