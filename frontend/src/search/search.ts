// The header search's rules (V1.1), kept apart from the components so they are easy to test.
//
//   SearchMode                     -> 'movies' | 'people': what the header searches
//   usableQuery(q)                 -> the trimmed text, or null under 2 letters or digits (the API's own rule:
//                                     nothing shorter is searched)
//   modeFromLocation(pathname)     -> the mode a results page stands for (/browse movies, /people people), else null
//   readStoredMode(), storeMode(m) -> the last mode used, in localStorage `search.mode` (default movies; storage
//                                     can be blocked, so both are wrapped)
//   resultsUrl(mode, q, keep?)     -> the full results page: /browse?…&q= (keeping browse's filters from `keep`,
//                                     back to page 1) or /people?q=
//   isTypingTarget(el)             -> true in an input, textarea, select or editable element, where "/" is typing
//   focusHeaderSearch()            -> the focus into the header's box (the people page asks for it with nothing to show)
export type SearchMode = 'movies' | 'people'

export const MODES: SearchMode[] = ['movies', 'people']
export const STORAGE_KEY = 'search.mode'
export const SEARCH_INPUT_ID = 'header-search'

export function focusHeaderSearch() {
  document.getElementById(SEARCH_INPUT_ID)?.focus()
}

export function usableQuery(q: string): string | null {
  const text = q.trim()
  return (text.match(/[\p{L}\p{N}]/gu) ?? []).length >= 2 ? text : null
}

export function modeFromLocation(pathname: string): SearchMode | null {
  return pathname === '/browse' ? 'movies' : pathname === '/people' ? 'people' : null
}

export function readStoredMode(): SearchMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'people' ? 'people' : 'movies'
  } catch {
    return 'movies'
  }
}

export function storeMode(mode: SearchMode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // blocked storage: the mode is simply not remembered
  }
}

const query = (pairs: [string, string][]) => pairs.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')

export function resultsUrl(mode: SearchMode, q: string, keep?: URLSearchParams): string {
  if (mode === 'people') return `/people?${query([['q', q.trim()]])}`
  const pairs = [...(keep ?? new URLSearchParams())].filter(([k]) => k !== 'q' && k !== 'page')
  return `/browse?${query([...pairs, ['q', q.trim()]])}`
}

export function isTypingTarget(el: Element | null): boolean {
  if (!el) return false
  if (el instanceof HTMLElement && el.isContentEditable) return true
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.getAttribute('contenteditable') === 'true'
}

/** "Actor · 42 films", or "Actor, Director" for several roles (most films first, as the API sends them). */
export function rolesLine(roles: { role: 'actor' | 'director' | 'writer'; n_films: number }[]): string {
  const label = { actor: 'Actor', director: 'Director', writer: 'Writer' }
  if (roles.length === 0) return ''
  if (roles.length > 1) return roles.map(r => label[r.role]).join(', ')
  const [{ role, n_films }] = roles
  return `${label[role]} · ${n_films} ${n_films === 1 ? 'film' : 'films'}`
}

export const count = (n: number, mode: SearchMode) =>
  `${n.toLocaleString('en-US')} ${mode === 'movies' ? (n === 1 ? 'movie' : 'movies') : n === 1 ? 'person' : 'people'}`
