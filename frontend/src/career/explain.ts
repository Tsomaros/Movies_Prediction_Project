// The track-record card's words, filled from the forecast's own numbers and the backtest of its role and metric
// (GET /people/{id}/career: metrics.<view>.forecast.explain and .test).
//
//   explainText(f, test, halfLife, metric) -> "How is this calculated?": scores to 1 decimal, box office with
//                                             money() (the typical box office is the weighted geometric mean, in
//                                             2025 $), shares as whole percents (the two add up to 100), the
//                                             half-life in whole years ("All films count equally." when it is
//                                             null), the backtest coverage as "N out of 10"
//   NOTES[metric]                          -> the note under it: which films we can see at all
//   hardToCall(test)                       -> revenue only (null for the score): how often a real next film's box
//                                             office was within 2× of the middle, beside the range's coverage
//   chartSummary(career, metric)           -> the chart's sentence for screen readers ("77 rated films from 1980 to
//                                             2025; average 6.8; best film X")
import type { CareerResponse, CareerView, ForecastTest } from '@/api/client'
import { money, points } from '@/result/format'

export const NOTES: Record<CareerView, string> = {
  score: "We only see the most-voted films of each year, so smaller films aren't counted.",
  revenue: 'Only films with a trusted box office count; many smaller films have none.',
}

type Numbers = { n_films: number; own_avg: number; own_share: number; db_avg: number; mid: number }

export function explainText(f: Numbers, test: { coverage: number }, halfLife: number | null, metric: CareerView): string {
  const own = Math.round(f.own_share * 100)
  const years = halfLife === null ? 0 : Math.round(halfLife)
  const weights = halfLife === null
    ? 'All films count equally.'
    : `Recent films count more: a film from ${years} ${years === 1 ? 'year' : 'years'} before the latest counts half.`
  const films = f.n_films === 1 ? 'film' : 'films'
  const [based, average, varies] = metric === 'score' ? [
    `Based on ${f.n_films} rated ${films}.`,
    `Their weighted average is ${points(f.own_avg)}; with this many films we trust it ${own}% and the database average (${points(f.db_avg)}) ${100 - own}%, giving ${points(f.mid)}.`,
    'The range is wider for people whose scores vary more.',
  ] : [
    `Based on ${f.n_films} ${films} with a trusted box office (in 2025 dollars).`,
    `Their typical box office is ${money(f.own_avg)}; with this many films we trust it ${own}% and the database's typical film (${money(f.db_avg)}) ${100 - own}%, giving ${money(f.mid)}.`,
    'The range is wider for people whose results vary more.',
  ]
  return [
    based, weights, average, varies,
    `In our tests on films from 2019 onward, ${Math.round(test.coverage * 10)} out of 10 real next films landed inside a range built this way.`,
  ].join(' ')
}

export function hardToCall(test: ForecastTest): string | null {
  if (test.within_2x == null) return null
  return `Box office is hard to call: in our tests only ${Math.round(test.within_2x * 100)}% of real next films landed within 2× of the middle, though ${Math.round(test.coverage * 100)}% fell inside the range.`
}

export function chartSummary(data: CareerResponse, metric: CareerView): string {
  const best = data.metrics[metric].best_film ? `; best film ${data.metrics[metric].best_film.title}` : ''
  if (metric === 'revenue') {
    const known = data.films.filter(f => f.revenue !== null)
    if (known.length === 0) return `${data.films.length} dated films, none with a known box office.`
    const typical = Math.exp(known.reduce((sum, f) => sum + Math.log(f.revenue!), 0) / known.length)
    return `${known.length} ${known.length === 1 ? 'film' : 'films'} with a known box office from ${known[0].year} to ${known[known.length - 1].year}; typical ${money(typical)}${best}`
  }
  const rated = data.films.filter(f => f.rated && f.score !== null)
  if (rated.length === 0) return `${data.films.length} dated films, none rated yet.`
  const average = rated.reduce((sum, f) => sum + f.score!, 0) / rated.length
  return `${rated.length} rated ${rated.length === 1 ? 'film' : 'films'} from ${rated[0].year} to ${rated[rated.length - 1].year}; average ${points(average)}${best}`
}
