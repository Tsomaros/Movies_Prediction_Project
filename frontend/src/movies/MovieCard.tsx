// One film in a grid, a row of the home page or the list view: poster, title, year and the score with its
// vote count ("7.4 (1,203 votes)"), so a high score from a handful of votes is visible as such.
import { StarIcon } from 'lucide-react'
import { Link } from 'react-router'

import type { MovieSummary } from '@/api/client'
import { votes } from '@/movies/people'
import { Poster } from '@/movies/Poster'
import { money } from '@/result/format'

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

export function MovieCard({ film, showRevenue = false }: { film: MovieSummary; showRevenue?: boolean }) {
  return (
    <Link to={`/movies/${film.id}`}
      className="group grid content-start gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
      <Poster poster={film.poster} title={film.title} />
      <span className="grid gap-0.5">
        <span className="line-clamp-2 text-sm font-medium leading-tight group-hover:underline">{film.title}</span>
        <span className="text-muted-foreground text-xs">{film.year ?? 'Year unknown'}</span>
        <span className="text-xs"><ScoreText score={film.score} votes={film.votes} /></span>
        {showRevenue && film.revenue_2025 != null && (
          <span className="text-xs tabular-nums">{money(film.revenue_2025)} worldwide</span>
        )}
      </span>
    </Link>
  )
}

export function MovieListItem({ film }: { film: MovieSummary }) {
  return (
    <Link to={`/movies/${film.id}`}
      className="hover:bg-accent/50 grid grid-cols-[3.5rem_1fr] items-center gap-3 rounded-md p-2 focus-visible:outline-2 focus-visible:outline-ring">
      <Poster poster={film.poster} title={film.title} />
      <span className="grid gap-0.5">
        <span className="font-medium">{film.title} <span className="text-muted-foreground font-normal">({film.year ?? '?'})</span></span>
        <span className="text-muted-foreground text-xs">{film.genres.join(', ') || 'No genre listed'}</span>
        <span className="text-xs"><ScoreText score={film.score} votes={film.votes} /></span>
      </span>
    </Link>
  )
}
