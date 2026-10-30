// What a film's release date says about it today (V1.2): the labels on cards and the film page.
//
//   releaseLabel(film, today)  -> { kind, text, hideScore, notRated }
//        a future date           -> kind 'coming', text "Coming 20 Nov" ("Coming 8 Jan 2027" in another year),
//                                   hideScore (there is no score to show yet)
//        out in the last 14 days -> kind 'new', text "New", notRated when it is below the 50-vote minimum
//        anything else           -> kind null (a card looks exactly as before)
//   localToday(now?)           -> today as "YYYY-MM-DD" in the visitor's time zone
//
// Dates are calendar dates ("2026-10-30"), compared and read as such, so no time zone moves one a day.
export type ReleaseLabel = { kind: 'new' | 'coming' | null; text: string | null; hideScore: boolean; notRated: boolean }

const NEW_DAYS = 14
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function localToday(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const day = (iso: string) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)))

export function releaseLabel(film: { release_date: string | null; score_ok: boolean }, today: string): ReleaseLabel {
  const none: ReleaseLabel = { kind: null, text: null, hideScore: false, notRated: false }
  const date = film.release_date
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return none
  if (date > today) {
    const year = date.slice(0, 4) === today.slice(0, 4) ? '' : ` ${date.slice(0, 4)}`
    return { kind: 'coming', text: `Coming ${Number(date.slice(8, 10))} ${MONTHS[Number(date.slice(5, 7)) - 1]}${year}`, hideScore: true, notRated: false }
  }
  if ((day(today) - day(date)) / 86_400_000 <= NEW_DAYS) return { kind: 'new', text: 'New', hideScore: false, notRated: !film.score_ok }
  return none
}
