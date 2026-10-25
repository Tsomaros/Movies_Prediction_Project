// Text for people and facts on the film pages.
//
//   initials(name)        -> "Robert Downey Jr." -> "RD", "Zendaya" -> "Z"
//   nameHue(name)         -> a hue 0-359 from the name, so a person's avatar has the same colour on every page
//   runtimeText(minutes)  -> 149 -> "2 h 29 min", 90 -> "1 h 30 min", 45 -> "45 min"
//   crewByJob(crew, jobs) -> [{job, people: [{id, name}]}] in the order of `jobs`, each person once
//   votes(n)              -> 1 -> "1 vote", 1203 -> "1,203 votes"
//   FILM_SORTS, readFilmSort(value), sortFilms(films, sort) -> the person page's film order (?sort=): newest
//                            first (the API's order), oldest, highest score or biggest box office; a film without
//                            the sorted value goes last
//   formatLife(born, died, today) -> "Born 9 Jul 1956 · 70", "1920–1990", "Died 1990", or null (dates are
//                            "YYYY-MM-DD", read as calendar dates: no time zone can move them a day)

import type { PersonDetail } from '@/api/client'

const SUFFIXES = new Set(['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'])

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(w => w && !SUFFIXES.has(w.toLowerCase()))
  if (words.length === 0) return '?'
  const first = [...words[0]][0] ?? ''
  const last = words.length > 1 ? [...words[words.length - 1]][0] ?? '' : ''
  return (first + last).toUpperCase()
}

export function nameHue(name: string): number {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)!) % 360
  return h
}

export function runtimeText(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h === 0 ? `${m} min` : m === 0 ? `${h} h` : `${h} h ${m} min`
}

export function crewByJob(crew: { id: number; name?: string | null; job: string }[], jobs: string[]) {
  return jobs.map(job => {
    const seen = new Set<number>()
    const people = crew.filter(c => c.job === job && c.name && !seen.has(c.id) && seen.add(c.id))
      .map(c => ({ id: c.id, name: c.name! }))
    return { job, people }
  }).filter(g => g.people.length > 0)
}

export const votes = (n: number) => `${n.toLocaleString('en-US')} ${n === 1 ? 'vote' : 'votes'}`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function parts(iso: string | null | undefined) {
  const m = iso ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso) : null
  return m ? { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) } : null
}

export function formatLife(born: string | null | undefined, died: string | null | undefined, today = new Date()): string | null {
  const b = parts(born)
  const d = parts(died)
  if (b && d) return `${b.y}–${d.y}`
  if (d) return `Died ${d.y}`
  if (!b) return null
  const [ty, tm, td] = [today.getFullYear(), today.getMonth() + 1, today.getDate()]
  const age = ty - b.y - (tm < b.m || (tm === b.m && td < b.d) ? 1 : 0)
  return `Born ${b.d} ${MONTHS[b.m - 1]} ${b.y} · ${age}`
}

type Film = PersonDetail['cast_credits'][number]
export type FilmSort = 'newest' | 'oldest' | 'score' | 'box_office'
export const FILM_SORTS: { value: FilmSort; label: string }[] = [
  { value: 'newest', label: 'Newest first' }, { value: 'oldest', label: 'Oldest first' },
  { value: 'score', label: 'Highest score' }, { value: 'box_office', label: 'Biggest box office' },
]
export const readFilmSort = (value: string | null): FilmSort =>
  FILM_SORTS.some(s => s.value === value) ? value as FilmSort : 'newest'

/** Films sorted for the grid; a film without the sorted value (no year, score or trusted revenue) goes last. */
export function sortFilms(films: Film[], sort: FilmSort): Film[] {
  if (sort === 'newest') return films // the API's order
  const key = (f: Film) => sort === 'oldest' ? (f.release_date ? -Date.parse(f.release_date) : null)
    : sort === 'score' ? (f.votes > 0 ? f.score : null) : f.revenue_2025
  return [...films].sort((a, b) => {
    const ka = key(a), kb = key(b)
    if (ka == null || kb == null) return ka == null ? (kb == null ? 0 : 1) : -1
    return kb - ka
  })
}

