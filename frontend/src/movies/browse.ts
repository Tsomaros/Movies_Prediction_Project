// The browse page's state lives in the URL, so a link or a refresh always shows the same page of films.
//
//   readBrowse(params)        -> the search, filters, sort and page from ?q=&genre=&from=&to=&lang=&score=&sort=&page=;
//                                anything malformed falls back to its default (never an error)
//   writeBrowse(state)        -> the same as URL parameters, defaults left out (a clean URL for the plain list)
//   browseResets(params, genres) -> what a link asked for that couldn't be used, in words ("genre", "page"), for
//                                a notice; an unknown genre (not in /meta/options) counts too
//   toQuery(state)            -> GET /movies's query for that state, PAGE_SIZE films a page
//   browseLink(partial)       -> a /browse link with some filters set (a curated row's "See all")
//   BROWSE_PARAMS             -> the parameter names above
//   activeFilters(state)      -> the filters in use, for "clear" chips and the no-results state
//   pageNumbers(page, pages)  -> the pager's numbers, null for a gap: (7, 20) -> [1, null, 6, 7, 8, null, 20]
//   loadView() / saveView(v)  -> the grid size or list view, remembered in this browser (try/catch: storage can fail)
//   GRID                      -> the grid's columns for each poster size
import type { MovieQuery, Sort } from '@/api/client'

export const PAGE_SIZE = 24
export const SORTS: { value: Sort; label: string }[] = [
  { value: 'popularity', label: 'Most popular' },
  { value: 'newest', label: 'Newest' },
  { value: 'title', label: 'Title A–Z' },
  { value: 'score', label: 'Highest score (50+ votes)' },
  { value: 'revenue', label: 'Biggest box office (2025 $)' },
]
export const SCORE_STEPS = [5, 6, 7, 8, 9] as const

export type BrowseState = {
  q: string
  genre: string | null
  yearFrom: number | null
  yearTo: number | null
  language: string | null
  scoreMin: number | null
  sort: Sort
  page: number
}

export const EMPTY: BrowseState = {
  q: '', genre: null, yearFrom: null, yearTo: null, language: null, scoreMin: null, sort: 'popularity', page: 1,
}

const KEYS = { q: 'q', genre: 'genre', yearFrom: 'from', yearTo: 'to', language: 'lang', scoreMin: 'score', sort: 'sort', page: 'page' } as const
/** The URL parameters of the browse page (an old /movies?… link carrying one is sent on to /browse). */
export const BROWSE_PARAMS: string[] = Object.values(KEYS)

function int(text: string | null, min: number, max: number): number | null {
  if (text === null || !/^\d+$/.test(text)) return null
  const n = Number(text)
  return n >= min && n <= max ? n : null
}

export function readBrowse(params: URLSearchParams): BrowseState {
  const sort = params.get(KEYS.sort)
  const score = Number(params.get(KEYS.scoreMin))
  const language = params.get(KEYS.language)
  return {
    q: (params.get(KEYS.q) ?? '').slice(0, 200),
    genre: params.get(KEYS.genre) || null,
    yearFrom: int(params.get(KEYS.yearFrom), 1900, 2100),
    yearTo: int(params.get(KEYS.yearTo), 1900, 2100),
    language: language && /^[a-z]{2}$/.test(language) ? language : null,
    scoreMin: params.has(KEYS.scoreMin) && Number.isFinite(score) && score > 0 && score <= 10 ? score : null,
    sort: SORTS.some(s => s.value === sort) ? (sort as Sort) : EMPTY.sort,
    page: int(params.get(KEYS.page), 1, 10_000) ?? 1,
  }
}

export function writeBrowse(state: BrowseState): URLSearchParams {
  const params = new URLSearchParams()
  for (const key of Object.keys(KEYS) as (keyof BrowseState)[]) {
    const value = state[key]
    if (value !== null && value !== '' && value !== EMPTY[key]) params.set(KEYS[key], String(value))
  }
  return params
}

const KEY_WORDS: Record<string, string> = {
  q: 'search', genre: 'genre', from: 'from year', to: 'to year', lang: 'language', score: 'score', sort: 'sort', page: 'page',
}

export function browseResets(params: URLSearchParams, genres: readonly string[] | undefined): string[] {
  const state = readBrowse(params)
  const used = writeBrowse(state)
  const out: string[] = []
  for (const [field, key] of Object.entries(KEYS) as [keyof BrowseState, string][]) {
    const raw = params.get(key)
    if (raw === null || raw === '' || field === 'q') continue
    const ok = used.get(key) === raw || String(EMPTY[field]) === raw || (field === 'scoreMin' && state.scoreMin === Number(raw))
    if (!ok || (field === 'genre' && genres && !genres.includes(raw))) out.push(KEY_WORDS[key])
  }
  return out
}

export function toQuery(state: BrowseState): MovieQuery {
  return {
    q: state.q.trim() || undefined,
    genre: (state.genre ?? undefined) as MovieQuery['genre'],
    year_from: state.yearFrom ?? undefined,
    year_to: state.yearTo ?? undefined,
    language: state.language ?? undefined,
    score_min: state.scoreMin ?? undefined,
    sort: state.sort,
    page: state.page,
    page_size: PAGE_SIZE,
  }
}

export function browseLink(partial: Partial<BrowseState>) {
  const params = writeBrowse({ ...EMPTY, ...partial })
  return params.size ? `/browse?${params}` : '/browse'
}

export type ActiveFilter = { key: keyof BrowseState; label: string }

export function activeFilters(state: BrowseState, languageName: (code: string) => string): ActiveFilter[] {
  const out: ActiveFilter[] = []
  if (state.q.trim()) out.push({ key: 'q', label: `“${state.q.trim()}”` })
  if (state.genre) out.push({ key: 'genre', label: state.genre })
  if (state.yearFrom !== null) out.push({ key: 'yearFrom', label: `From ${state.yearFrom}` })
  if (state.yearTo !== null) out.push({ key: 'yearTo', label: `To ${state.yearTo}` })
  if (state.language) out.push({ key: 'language', label: languageName(state.language) })
  if (state.scoreMin !== null) out.push({ key: 'scoreMin', label: `Score ${state.scoreMin}+` })
  return out
}

export type View = 'small' | 'medium' | 'large' | 'list'
export const VIEWS: View[] = ['small', 'medium', 'large', 'list']
export const GRID: Record<Exclude<View, 'list'>, string> = {
  small: 'grid-cols-3 sm:grid-cols-5 lg:grid-cols-6',
  medium: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4',
  large: 'grid-cols-2 lg:grid-cols-3',
}
export const VIEW_KEY = 'movie-prediction:view'

export function loadView(): View {
  try {
    const v = localStorage.getItem(VIEW_KEY)
    return VIEWS.includes(v as View) ? (v as View) : 'medium'
  } catch {
    return 'medium'
  }
}

export function saveView(view: View) {
  try {
    localStorage.setItem(VIEW_KEY, view)
  } catch { /* blocked storage: the choice lasts for this visit only */ }
}

/** The page numbers to show, with null for a gap: (7, 20) -> [1, null, 6, 7, 8, null, 20]. */
export function pageNumbers(current: number, pages: number, around = 1): (number | null)[] {
  const keep = new Set([1, pages])
  for (let p = current - around; p <= current + around; p++) if (p >= 1 && p <= pages) keep.add(p)
  const sorted = [...keep].sort((a, b) => a - b)
  const out: (number | null)[] = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] === 2) out.push(p - 1) // a gap of one page: show the page, not "…"
    else if (i > 0 && p - sorted[i - 1] > 2) out.push(null)
    out.push(p)
  })
  return out
}
