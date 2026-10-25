// The track-record card's "How is this calculated?" paragraph, filled from the forecast's own numbers and the
// backtest of its role (GET /people/{id}/career: forecast.explain and forecast.test).
//
//   explainText(f, test, halfLife)  -> the paragraph: scores to 1 decimal, shares as whole percents (the two add
//                                      up to 100), the half-life in whole years ("All films count equally." when
//                                      it is null), the backtest coverage as "N out of 10"
//   MOST_VOTED_NOTE                 -> the note under it: which films we can see at all
//   chartSummary(career)            -> the chart's sentence for screen readers ("23 rated films from 1999 to 2024;
//                                      average 6.9; best film X")
import type { CareerResponse } from '@/api/client'
import { points } from '@/result/format'

export const MOST_VOTED_NOTE = "We only see the most-voted films of each year, so smaller films aren't counted."

type Numbers = { n_rated: number; own_avg: number; own_share: number; db_avg: number; mid: number }

export function explainText(f: Numbers, test: { coverage: number }, halfLife: number | null): string {
  const own = Math.round(f.own_share * 100)
  const years = halfLife === null ? 0 : Math.round(halfLife)
  const weights = halfLife === null
    ? 'All films count equally.'
    : `Recent films count more: a film from ${years} ${years === 1 ? 'year' : 'years'} before the latest counts half.`
  return [
    `Based on ${f.n_rated} rated ${f.n_rated === 1 ? 'film' : 'films'}.`,
    weights,
    `Their weighted average is ${points(f.own_avg)}; with this many films we trust it ${own}% and the database average (${points(f.db_avg)}) ${100 - own}%, giving ${points(f.mid)}.`,
    'The range is wider for people whose scores vary more.',
    `In our tests on films from 2019 onward, ${Math.round(test.coverage * 10)} out of 10 real next films landed inside a range built this way.`,
  ].join(' ')
}

export function chartSummary(data: CareerResponse): string {
  const rated = data.films.filter(f => f.rated && f.score !== null)
  if (rated.length === 0) return `${data.films.length} dated films, none rated yet.`
  const average = rated.reduce((sum, f) => sum + f.score!, 0) / rated.length
  const best = data.best_film ? `; best film ${data.best_film.title}` : ''
  return `${rated.length} rated ${rated.length === 1 ? 'film' : 'films'} from ${rated[0].year} to ${rated[rated.length - 1].year}; average ${points(average)}${best}`
}
