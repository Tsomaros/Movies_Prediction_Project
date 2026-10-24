// /my-movies keeps its tab, sort and page in the URL (?tab=&sort=&page=), so a link or the back button shows
// the same list.
//
//   readMyMovies(params)   -> {tab, sort, page}; anything unknown falls back to its default (watched, added, 1),
//                             and a sort the tab doesn't offer (rating on the watchlist) to "added"
//   writeMyMovies(state)   -> the same as URL parameters, defaults left out
//   TABS, SORTS_FOR(tab)   -> the tabs and each list's sorts, with labels
import type { MySort, Status } from '@/api/client'

export type Tab = Status | 'notes'
export type MyMoviesState = { tab: Tab; sort: MySort; page: number }

export const TABS: { value: Tab; label: string }[] = [
  { value: 'watched', label: 'Watched' },
  { value: 'plan_to_watch', label: 'Plan to watch' },
  { value: 'notes', label: 'Notes' },
]
const SORTS: { value: MySort; label: string }[] = [
  { value: 'added', label: 'Date added' },
  { value: 'title', label: 'Title A–Z' },
  { value: 'rating', label: 'Your rating' },
  { value: 'watched', label: 'Watched date' },
]
export const SORTS_FOR = (tab: Tab) => tab === 'watched' ? SORTS : SORTS.filter(s => s.value === 'added' || s.value === 'title')

export const MY_DEFAULTS: MyMoviesState = { tab: 'watched', sort: 'added', page: 1 }

export function readMyMovies(params: URLSearchParams): MyMoviesState {
  const tab = TABS.find(t => t.value === params.get('tab'))?.value ?? MY_DEFAULTS.tab
  const sort = SORTS_FOR(tab).find(s => s.value === params.get('sort'))?.value ?? MY_DEFAULTS.sort
  const page = Number(params.get('page'))
  return { tab, sort, page: Number.isInteger(page) && page >= 1 && page <= 1000 ? page : 1 }
}

export function writeMyMovies(state: MyMoviesState): string {
  const params = new URLSearchParams()
  if (state.tab !== MY_DEFAULTS.tab) params.set('tab', state.tab)
  if (state.sort !== MY_DEFAULTS.sort && state.tab !== 'notes') params.set('sort', state.sort)
  if (state.page !== 1) params.set('page', String(state.page))
  return params.toString()
}
