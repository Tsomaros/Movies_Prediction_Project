// /people/:id: one person (Day 14.6; crew roles Day 14.7). TMDB's photo, life dates, birthplace and biography when
// the person pull found them (otherwise an initials avatar), then, for one role at a time (acting, directing,
// writing, production, music, camera, editing; a switch in ?role= when they have several, opening on their main
// role): a stats strip from our own data, the Career section (acting, directing and writing: a chart and two
// forecasts, loaded on demand with its chart library) and their films as a poster grid (the character they
// played, or their writing credit), sorted by ?sort=. "Predict a film with this actor / director" starts a fresh form with them in
// that slot; other roles have no form field. The biography is plain text: blank lines make paragraphs, never HTML.
import { ArrowLeftIcon, ExternalLinkIcon, SparklesIcon } from 'lucide-react'
import { lazy, Suspense, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError, type CareerRole, type PersonDetail } from '@/api/client'
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

type Role = PersonDetail['roles'][number]
type RoleName = Role['role']
const ROLE_TEXT: Record<RoleName, { noun: string; verb?: string; cast: string }> = {
  acting: { noun: 'Actor', cast: 'Most often with' },
  directing: { noun: 'Director', verb: 'Directed', cast: 'Most often cast' },
  writing: { noun: 'Writer', verb: 'Wrote', cast: 'Most often with' },
  production: { noun: 'Producer', verb: 'Produced', cast: 'Most often with' },
  music: { noun: 'Composer', verb: 'Scored', cast: 'Most often with' },
  camera: { noun: 'Cinematographer', verb: 'Shot', cast: 'Most often with' },
  editing: { noun: 'Editor', verb: 'Edited', cast: 'Most often with' },
}
const CareerSection = lazy(() => import('@/career/CareerSection'))
const CAREER_ROLES: readonly string[] = ['acting', 'directing', 'writing'] satisfies CareerRole[]
const PREDICT_AS: Partial<Record<RoleName, 'actor' | 'director'>> = { acting: 'actor', directing: 'director' }
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

function Stats({ role }: { role: Role }) {
  const s = role.stats
  const text = ROLE_TEXT[role.role]
  const chips: { key: string; content: ReactNode }[] = []
  if (s.film_count > 0) {
    const years = s.first_year == null ? '' : s.first_year === s.last_year ? ` · ${s.first_year}` : ` · ${s.first_year}–${s.last_year}`
    const films = `${s.film_count} ${s.film_count === 1 ? 'film' : 'films'}`
    chips.push({ key: 'films', content: `${text.verb ? `${text.verb} ${films}` : films}${years}` })
  }
  if (s.top_genres.length > 0) chips.push({ key: 'genres', content: `Mostly ${s.top_genres.map(g => g.name).join(', ')}` })
  if (s.avg_score) chips.push({ key: 'score', content: `Average score ${points(s.avg_score.value)} from ${s.avg_score.films} ${s.avg_score.films === 1 ? 'film' : 'films'}` })
  if (s.box_office_2025) {
    const b = s.box_office_2025
    chips.push({ key: 'money', content: `${money(b.total)} box office (2025 $) from ${b.films} of ${b.of} films` })
  }
  for (const [key, label, ref] of [['actor', text.cast, s.top_actor], ['director', 'Most often directed by', s.top_director]] as const) {
    if (ref) chips.push({ key, content: <>{label} <Link to={`/people/${ref.id}`} className="font-medium underline">{ref.name}</Link> ({ref.shared_films} films)</> })
  }
  if (chips.length === 0) return null
  return (
    <ul aria-label="Stats" className="flex flex-wrap gap-2">
      {chips.map(c => <li key={c.key} className="bg-secondary text-secondary-foreground rounded-full px-3 py-1 text-sm">{c.content}</li>)}
    </ul>
  )
}

function RoleSwitch({ roles, value, onChange }: { roles: Role[]; value: RoleName; onChange: (r: RoleName) => void }) {
  return (
    <div role="radiogroup" aria-label="Show their work as" className="bg-muted inline-flex max-w-full flex-wrap gap-0.5 rounded-md p-0.5">
      {roles.map(r => (
        <button key={r.role} type="button" role="radio" aria-checked={value === r.role} onClick={() => onChange(r.role)}
          className={cn('inline-flex h-8 items-center gap-1.5 rounded px-2.5 text-sm',
            value === r.role ? 'bg-background font-medium shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
          {r.label} <span className="text-muted-foreground text-xs tabular-nums">{r.films.length}</span>
        </button>
      ))}
    </div>
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
  const setParam = (key: 'role' | 'sort', value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true, preventScrollReset: true })
  }

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
  const main = p.roles.find(r => r.role === p.main_role) ?? p.roles[0]
  const role = p.roles.find(r => r.role === params.get('role')) ?? main
  const films = role ? sortFilms(role.films, sort) : []
  const predictAs = role ? PREDICT_AS[role.role] : undefined
  const predict = () => navigate(`/predict?${new URLSearchParams({
    [URL_PARAM]: encodeForm(personToForm({ id: p.id, name }, predictAs)), [LIKE_PARAM]: name })}`)
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
            {main && <p className="text-muted-foreground text-sm">{ROLE_TEXT[main.role].noun}</p>}
          </div>
          {(life || p.place_of_birth) && <p className="text-sm">{[life, p.place_of_birth].filter(Boolean).join(' · ')}</p>}
          {p.roles.length > 1 && role && (
            <RoleSwitch roles={p.roles} value={role.role} onChange={r => setParam('role', r === main?.role ? null : r)} />
          )}
          {role && <Stats role={role} />}
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
          {predictAs && (
            <div>
              <Button onClick={predict}><SparklesIcon /> Predict a film with this {predictAs}</Button>
              <p className="text-muted-foreground mt-1 text-xs">
                Opens the form with {name} as the {predictAs === 'actor' ? 'lead' : 'director'}; you fill in the rest.
              </p>
            </div>
          )}
        </div>
      </div>

      {role && (CAREER_ROLES.includes(role.role) ? (
        <Suspense fallback={<Skeleton className="h-72" />}>
          <CareerSection key={`${p.id}-${role.role}`} personId={p.id} name={name} role={role.role as CareerRole} />
        </Suspense>
      ) : (
        <p className="text-muted-foreground text-sm">The career chart covers acting, directing and writing.</p>
      ))}

      {role && (
        <section aria-labelledby="films-heading" className="grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="films-heading" className="text-lg font-semibold">{role.role === 'acting' ? 'Films' : `Films · ${role.label}`}</h2>
            <FilterSelect label="Sort films" value={sort} className="bg-card h-8 w-44" choices={FILM_SORTS}
              onChange={s => setParam('sort', s && s !== 'newest' ? s : null)} />
          </div>
          <ul className={cn('grid gap-4', GRID.medium)} aria-label="Films">
            {films.map((f, i) => (
              <li key={f.id}><MovieCard film={f} eager={i < 4}
                subtitle={f.character ? `as ${f.character}` : role.role === 'writing' ? f.jobs.join(', ') : undefined} /></li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-muted-foreground border-t pt-4 text-xs">
        Data from TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.
      </p>
    </article>
  )
}
