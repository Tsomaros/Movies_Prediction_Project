// /people/:id: one person (Day 14.6; crew roles Day 14.7). TMDB's photo, life dates, birthplace and biography when
// the person pull found them (otherwise an initials avatar), then, for one role at a time (acting, directing,
// writing, production, music, camera, editing; a switch in ?role= when they have several, opening on their main
// role): a stats strip from our own data, the Career section (acting, directing and writing: a chart and two
// forecasts, loaded on demand with its chart library) and their films as a poster grid (the character they
// played, or their writing credit), sorted by ?sort=. "Predict a film with this actor / director" starts a fresh form with them in
// that slot; other roles have no form field. The biography is plain text: blank lines make paragraphs, never HTML.
// The page's parts live in src/movies/person/.
import { ArrowLeftIcon, ExternalLinkIcon, SparklesIcon } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'

import { ApiError, type CareerRole } from '@/api/client'
import { usePerson } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { encodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { FilterSelect } from '@/movies/Filters'
import { FILM_SORTS, formatLife, initials, nameHue, readFilmSort, sortFilms } from '@/movies/people'
import { Biography } from '@/movies/person/Biography'
import { FilmGrid } from '@/movies/person/FilmGrid'
import { RoleSwitch } from '@/movies/person/RoleSwitch'
import { ROLE_TEXT, type RoleName } from '@/movies/person/roles'
import { Stats } from '@/movies/person/Stats'
import { personToForm } from '@/movies/predictLike'

const CareerSection = lazy(() => import('@/career/CareerSection'))
const CAREER_ROLES: readonly string[] = ['acting', 'directing', 'writing'] satisfies CareerRole[]
const PREDICT_AS: Partial<Record<RoleName, 'actor' | 'director'>> = { acting: 'actor', directing: 'director' }

function Avatar({ name }: { name: string }) {
  return (
    <span aria-hidden className="flex aspect-[2/3] w-full items-center justify-center rounded-md text-4xl font-semibold text-white"
      style={{ backgroundColor: `hsl(${nameHue(name)} 45% 38%)` }}>
      {initials(name)}
    </span>
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
          <FilmGrid films={films} writing={role.role === 'writing'} />
        </section>
      )}

      <p className="text-muted-foreground border-t pt-4 text-xs">
        Data from TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.
      </p>
    </article>
  )
}
