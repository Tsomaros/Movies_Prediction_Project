// One film in a grid, a row of the home page or the list view: poster, title, year and the score with its
// vote count ("7.4 (1,203 votes)"), so a high score from a handful of votes is visible as such.
// For a logged-in visitor a card (and a list-view row) can also show its list status (`entry`: a badge on the
// poster) and the quick list buttons (`quick`), which sit beside the link, never inside it. `subtitle` adds a line under the title (the
// person page's "as Forrest"). V1.2: a film out in the last 14 days wears a "New" tag on its poster ("Not rated yet"
// under 50 votes), a film not yet released shows "Coming 20 Nov" instead of a score (src/movies/release.ts).
import { StarIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { Entry, MovieSummary } from '@/api/client'
import { cn } from '@/lib/utils'
import { QuickButtons, StatusBadge } from '@/me/CardStatus'
import { votes } from '@/movies/people'
import { Poster } from '@/movies/Poster'
import { money } from '@/result/format'
import { localToday, releaseLabel, type ReleaseLabel } from '@/movies/release'

export function ScoreText({ score, votes: n }: { score: number | null | undefined; votes: number }) {
  if (score == null || n === 0) return <span className="text-muted-foreground">No votes yet</span>
  return (
    <span className="inline-flex items-center gap-1 tabular-nums">
      <StarIcon className="size-3.5 fill-amber-400 text-amber-500" aria-hidden />
      <span className="font-medium">{score.toFixed(1)}</span>
      <span className="text-muted-foreground">({votes(n)})</span>
    </span>
  )
}

/** The "New" tag in a poster's top-right corner (the list-status badge has the top-left). */
function NewTag({ label }: { label: ReleaseLabel }) {
  if (label.kind !== 'new') return null
  return (
    <span className="absolute top-1.5 right-1.5 rounded bg-rose-600 px-1.5 py-0.5 text-[0.65rem] font-semibold tracking-wide text-white uppercase shadow-xs">
      {label.text}
    </span>
  )
}

/** Under the title: the score, or what replaces it for a new or coming film. */
function ScoreLine({ film, label }: { film: MovieSummary; label: ReleaseLabel }) {
  if (label.kind === 'coming') return <span className="text-muted-foreground">{label.text}</span>
  if (label.notRated) return <span className="text-muted-foreground">Not rated yet</span>
  return <ScoreText score={film.score} votes={film.votes} />
}

export function MovieCard({ film, showRevenue = false, eager = false, entry, quick = false, subtitle }: {
  film: MovieSummary; showRevenue?: boolean; eager?: boolean; entry?: Entry; quick?: boolean; subtitle?: string
}) {
  const label = releaseLabel(film, localToday())
  return (
    <div className="group/card relative">
    <Link to={`/movies/${film.id}`}
      className="group grid content-start gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
      <span className="relative block">
        <Poster poster={film.poster} title={film.title} eager={eager} />
        {entry && <StatusBadge entry={entry} />}
        <NewTag label={label} />
      </span>
      <span className="grid gap-0.5">
        <span className="line-clamp-2 text-sm font-medium leading-tight group-hover:underline">{film.title}</span>
        {subtitle && <span className="text-muted-foreground line-clamp-2 text-xs italic">{subtitle}</span>}
        <span className="text-muted-foreground text-xs">{film.year ?? 'Year unknown'}</span>
        <span className="text-xs"><ScoreLine film={film} label={label} /></span>
        {showRevenue && film.revenue_2025 != null && (
          <span className="text-xs tabular-nums">{money(film.revenue_2025)} worldwide</span>
        )}
      </span>
    </Link>
    {quick && <QuickButtons movieId={film.id} title={film.title} entry={entry} />}
    </div>
  )
}

export function MovieListItem({ film, eager = false, entry, quick = false }: {
  film: MovieSummary; eager?: boolean; entry?: Entry; quick?: boolean
}) {
  const label = releaseLabel(film, localToday())
  return (
    <div className="group/card relative">
    <Link to={`/movies/${film.id}`}
      className={cn('hover:bg-accent/50 grid grid-cols-[3.5rem_1fr] items-center gap-3 rounded-md p-2 focus-visible:outline-2 focus-visible:outline-ring',
        quick && 'pr-20')}>
      <span className="relative block">
        <Poster poster={film.poster} title={film.title} eager={eager} />
        {entry && <StatusBadge entry={entry} />}
        <NewTag label={label} />
      </span>
      <span className="grid gap-0.5">
        <span className="font-medium">{film.title} <span className="text-muted-foreground font-normal">({film.year ?? '?'})</span></span>
        <span className="text-muted-foreground text-xs">{film.genres.join(', ') || 'No genre listed'}</span>
        <span className="text-xs"><ScoreLine film={film} label={label} /></span>
      </span>
    </Link>
    {quick && <QuickButtons movieId={film.id} title={film.title} entry={entry}
      className="absolute top-1/2 right-2 -translate-y-1/2" />}
    </div>
  )
}
