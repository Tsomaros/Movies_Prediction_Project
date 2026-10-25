// /movies/:id: one film. Facts and overview, the score with its votes, the money as reported or in 2025 dollars,
// the cast (TMDB photos where the person pull has one, initials otherwise) and key crew, similar films, and "Predict a film like this",
// which opens the creator form pre-filled (src/movies/predictLike.ts). Your lists (watched with a date and a
// 10-star rating, or plan to watch) sit under the score, and your private notes after the overview.
// Cast and crew names link to their person pages (/people/:id).
import { ArrowLeftIcon, ExternalLinkIcon, SparklesIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError, type MovieDetail as Film } from '@/api/client'
import { useMetaOptions, useMovie } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { codeName } from '@/form/format'
import { encodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { cn } from '@/lib/utils'
import { FilmNotes } from '@/me/FilmNotes'
import { useStatuses } from '@/me/hooks'
import { ListControl } from '@/me/ListControl'
import { ScoreText } from '@/movies/MovieCard'
import { crewByJob, initials, nameHue, runtimeText } from '@/movies/people'
import { Poster } from '@/movies/Poster'
import { filmToForm } from '@/movies/predictLike'
import { money, points } from '@/result/format'

const CREW_JOBS = ['Director', 'Screenplay', 'Writer', 'Producer', 'Original Music Composer', 'Director of Photography', 'Editor']
const JOB_LABELS: Record<string, string> = { 'Original Music Composer': 'Music', 'Director of Photography': 'Cinematography' }
const MAX_PER_JOB = 4

function Avatar({ name, photo }: { name: string; photo?: Film['cast'][number]['photo'] }) {
  if (photo) return <img src={photo.small} alt="" loading="lazy" decoding="async" className="bg-muted size-12 shrink-0 rounded-full object-cover" />
  return (
    <span aria-hidden className="inline-flex size-12 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
      style={{ backgroundColor: `hsl(${nameHue(name)} 45% 38%)` }}>
      {initials(name)}
    </span>
  )
}

function Chips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <ul aria-label={label} className="flex flex-wrap gap-1.5">
      {items.map(i => <li key={i} className="bg-secondary text-secondary-foreground rounded-full px-2.5 py-0.5 text-xs">{i}</li>)}
    </ul>
  )
}

function MoneyPanel({ film }: { film: Film }) {
  const [inflated, setInflated] = useState(true)
  const m = film.money
  const rows = [
    { label: 'Budget', value: inflated ? m.budget_2025 : m.budget },
    { label: 'Worldwide box office', value: inflated ? m.revenue_2025 : m.revenue },
  ]
  return (
    <section aria-labelledby="money-heading" className="bg-card grid content-start gap-3 self-start rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="money-heading" className="font-semibold">Money</h2>
        <div role="radiogroup" aria-label="Show money" className="bg-muted inline-flex rounded-md p-0.5 text-xs">
          {[{ v: false, label: 'As reported' }, { v: true, label: 'In 2025 dollars' }].map(o => (
            <button key={o.label} type="button" role="radio" aria-checked={inflated === o.v} onClick={() => setInflated(o.v)}
              className={cn('rounded px-2 py-1', inflated === o.v ? 'bg-background shadow-xs' : 'text-muted-foreground')}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <dl className="grid gap-1 text-sm">
        {rows.map(r => (
          <div key={r.label} className="flex justify-between gap-4">
            <dt className="text-muted-foreground">{r.label}</dt>
            <dd className={r.value == null ? 'text-muted-foreground italic' : 'font-medium tabular-nums'}>
              {r.value == null ? 'not reported' : money(r.value)}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-muted-foreground text-xs">
        {inflated ? 'Adjusted to 2025 US dollars with the US consumer price index.' : `US dollars of ${film.year ?? 'the release year'}, as TMDB reports them.`}
      </p>
      {m.suspect && (
        <p className="rounded-md bg-amber-50 px-2 py-1 text-xs dark:bg-amber-950/30">
          Our cleaning rules doubt these figures{m.suspect_reason ? ` (${m.suspect_reason})` : ''}, so the models never learn from them.
        </p>
      )}
      {m.revenue_incomplete && (
        <p className="text-muted-foreground text-xs">Released less than six months before our data was pulled: the box office may still grow.</p>
      )}
    </section>
  )
}

function Loading() {
  return (
    <div className="grid gap-6 sm:grid-cols-[14rem_1fr]" aria-busy="true">
      <span className="sr-only">Loading the film…</span>
      <Skeleton className="aspect-[2/3]" />
      <div className="grid content-start gap-3"><Skeleton className="h-9 w-2/3" /><Skeleton className="h-5 w-1/2" /><Skeleton className="h-32" /></div>
    </div>
  )
}

export function NotFoundFilm() {
  return (
    <div className="grid justify-items-start gap-4">
      <title>Film not found · Movie Prediction</title>
      <h1 className="text-2xl font-semibold">We don't have this film</h1>
      <p className="text-muted-foreground">The link may be wrong, or the film isn't in our TMDB data.</p>
      <div className="flex gap-2">
        <Button asChild><Link to="/browse">Search films</Link></Button>
        <Button asChild variant="outline"><Link to="/">Start page</Link></Button>
      </div>
    </div>
  )
}

export default function MovieDetail() {
  const { id } = useParams()
  const movieId = id && /^\d+$/.test(id) ? Number(id) : null
  const film = useMovie(movieId)
  const options = useMetaOptions()
  const navigate = useNavigate()
  const yours = useStatuses(movieId === null ? [] : [movieId]).get(movieId ?? -1)

  if (movieId === null || (film.error instanceof ApiError && film.error.kind === 'not_found')) return <NotFoundFilm />
  if (film.isError) {
    return (
      <div role="alert" className="grid justify-items-start gap-3">
        <p>The film couldn't load: {film.error.message}</p>
        <Button variant="outline" onClick={() => film.refetch()}>Try again</Button>
      </div>
    )
  }
  if (!film.data) return <><SlowNotice pending /><Loading /></>

  const f = film.data
  const crew = crewByJob(f.crew, CREW_JOBS)
  const facts = [
    f.certification, f.runtime ? runtimeText(f.runtime) : null, f.release_date,
    f.original_language ? codeName('language', f.original_language) : null,
  ].filter(Boolean)
  const predictLike = () => {
    if (!options.data) return
    navigate(`/predict?${new URLSearchParams({ [URL_PARAM]: encodeForm(filmToForm(f, options.data)), [LIKE_PARAM]: f.title })}`)
  }

  return (
    <article className="grid gap-8">
      <title>{`${f.title}${f.year ? ` (${f.year})` : ''} · Movie Prediction`}</title>
      <Link to="/browse" className="text-muted-foreground inline-flex w-fit items-center gap-1 text-sm hover:underline">
        <ArrowLeftIcon className="size-4" aria-hidden /> Browse films
      </Link>

      <div className="grid gap-6 sm:grid-cols-[14rem_1fr]">
        <Poster poster={f.poster} title={f.title} size="large" eager className="mx-auto w-48 sm:w-full" />
        <div className="grid content-start gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              {f.title} {f.year && <span className="text-muted-foreground font-normal">({f.year})</span>}
            </h1>
            {f.original_title && f.original_title !== f.title && <p className="text-muted-foreground text-sm">{f.original_title}</p>}
            {f.tagline && <p className="text-muted-foreground mt-1 italic">{f.tagline}</p>}
          </div>
          {facts.length > 0 && <p className="text-sm">{facts.join(' · ')}</p>}
          <p className="text-sm" data-testid="film-score">
            <ScoreText score={f.rating.average} votes={f.rating.votes} />
            {f.rating.votes > 0 && !f.rating.usable && (
              <span className="text-muted-foreground"> · fewer than 50 votes, so our models don't use this score</span>
            )}
            {yours?.rating != null && <span data-testid="film-your-rating"> · You: <span className="font-medium">{yours.rating}/10</span></span>}
          </p>
          <ListControl movieId={f.id} />
          <Chips label="Genres" items={f.genres} />
          <Chips label="Themes" items={f.themes} />
          {f.overview && <p className="max-w-prose">{f.overview}</p>}
          <div>
            <Button onClick={predictLike} disabled={!options.data}><SparklesIcon /> Predict a film like this</Button>
            <p className="text-muted-foreground mt-1 text-xs">Opens the form with its genres, themes, runtime, language, rating, director and top cast.</p>
          </div>
        </div>
      </div>

      <FilmNotes movieId={f.id} />

      <div className="grid gap-6 md:grid-cols-[1fr_20rem]">
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
        <MoneyPanel film={f} />
      </div>

      {f.cast.length > 0 && (
        <section aria-labelledby="cast-heading" className="grid gap-3">
          <h2 id="cast-heading" className="text-lg font-semibold">Cast</h2>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {f.cast.map(c => (
              <li key={`${c.id}-${c.order}`} className="flex items-center gap-3">
                <Avatar name={c.name ?? '?'} photo={c.photo} />
                <span className="grid">
                  <Link to={`/people/${c.id}`} className="font-medium hover:underline">{c.name}</Link>
                  {c.character && <span className="text-muted-foreground text-sm">{c.character}</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {f.similar.length > 0 && (
        <section aria-labelledby="similar-heading" className="grid gap-3">
          <h2 id="similar-heading" className="text-lg font-semibold">Similar films</h2>
          <ul className="grid grid-cols-3 gap-4 sm:grid-cols-6">
            {f.similar.map(s => (
              <li key={s.id}>
                <Link to={`/movies/${s.id}`} className="group grid gap-1.5 rounded-md focus-visible:outline-2 focus-visible:outline-ring">
                  <Poster poster={s.poster} title={s.title} />
                  <span className="text-sm leading-tight group-hover:underline">{s.title}</span>
                  <span className="text-muted-foreground text-xs">{s.year} · {points(s.score)}</span>
                  {s.why[0] && <span className="text-muted-foreground text-[11px]">{s.why[0]}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-muted-foreground border-t pt-4 text-xs">
        Data from TMDB.{' '}
        <a href={`https://www.themoviedb.org/movie/${f.id}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline">
          This film on TMDB <ExternalLinkIcon className="size-3" aria-hidden />
        </a>
      </p>
    </article>
  )
}
