// Words for the live new and upcoming films (V1.2). Dates are calendar dates ("2026-11-14"), read as such so a
// time zone can never move them a day.
//
//   shortDate(iso)           -> "Nov 14"
//   longDate(iso)            -> "Nov 14, 2026"
//   statusBadge(film)        -> "Out today", "New", or the release date for an upcoming film
//   footerLabel(film)        -> the score ("7.4"), else "Not rated yet" (out) or "Coming Nov 14" (upcoming)
//   releaseLine(film)        -> "Released Oct 24, 2026" or "In cinemas Nov 14, 2026"
//   updatedAgo(iso, now?)    -> "Updated 2 hours ago"
import type { LiveMovie } from '@/api/client'

type Dated = Pick<LiveMovie, 'release_date'>

function parts(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

export const shortDate = (iso: string) =>
  parts(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

export const longDate = (iso: string) =>
  parts(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })

export function statusBadge(film: Pick<LiveMovie, 'status'> & Dated): string {
  return film.status === 'out_today' ? 'Out today' : film.status === 'new' ? 'New' : shortDate(film.release_date)
}

export function footerLabel(film: Pick<LiveMovie, 'status' | 'vote_average'> & Dated): string {
  if (film.vote_average != null) return film.vote_average.toFixed(1)
  return film.status === 'upcoming' ? `Coming ${shortDate(film.release_date)}` : 'Not rated yet'
}

export const releaseLine = (film: Pick<LiveMovie, 'status'> & Dated) =>
  `${film.status === 'upcoming' ? 'In cinemas' : 'Released'} ${longDate(film.release_date)}`

export function updatedAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return ''
  const minutes = Math.max(0, Math.floor((now - Date.parse(iso)) / 60000))
  if (minutes < 1) return 'Updated just now'
  if (minutes < 60) return `Updated ${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago`
  const hours = Math.round(minutes / 60)
  return `Updated ${hours} ${hours === 1 ? 'hour' : 'hours'} ago`
}
