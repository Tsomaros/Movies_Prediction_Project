// /movies/:id: one film. Facts and overview, the score with its votes, the money as reported or in 2025 dollars,
// the cast (TMDB photos where the person pull has one, initials otherwise) and key crew, similar films, and "Predict a film like this",
// which opens the creator form pre-filled (src/movies/predictLike.ts). Your lists (watched with a date and a
// 10-star rating, or plan to watch) sit under the score, and your private notes after the overview.
// Cast and crew names link to their person pages (/people/:id). The sections live in src/movies/film/.
import { ArrowLeftIcon, ExternalLinkIcon, SparklesIcon } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError } from '@/api/client'
import { useMetaOptions, useMovie } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { codeName } from '@/form/format'
import { encodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { FilmNotes } from '@/me/FilmNotes'
import { useStatuses } from '@/me/hooks'
import { ListControl } from '@/me/ListControl'
import { CastList } from '@/movies/film/CastList'
import { MadeBy } from '@/movies/film/MadeBy'
import { MoneyPanel } from '@/movies/film/MoneyPanel'
import { SimilarFilms } from '@/movies/film/SimilarFilms'
import { ScoreText } from '@/movies/MovieCard'
import { runtimeText } from '@/movies/people'
import { Poster } from '@/movies/Poster'
import { filmToForm } from '@/movies/predictLike'

function Chips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <ul aria-label={label} className="flex flex-wrap gap-1.5">
      {items.map(i => <li key={i} className="bg-secondary text-secondary-foreground rounded-full px-2.5 py-0.5 text-xs">{i}</li>)}
    </ul>
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
        <MadeBy film={f} />
        <MoneyPanel film={f} />
      </div>

      <CastList cast={f.cast} />
      <SimilarFilms films={f.similar} />

      <p className="text-muted-foreground border-t pt-4 text-xs">
        Data from TMDB.{' '}
        <a href={`https://www.themoviedb.org/movie/${f.id}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline">
          This film on TMDB <ExternalLinkIcon className="size-3" aria-hidden />
        </a>
      </p>
    </article>
  )
}
