// "Surprise me" choices the browser remembers: the source, the filters and "Include hidden gems".
//
//   loadPrefs() / savePrefs(prefs)  -> localStorage, wrapped so blocked storage is just "the defaults"; every field
//                                      is checked on load and a bad one falls back to its default
//   toQuery(prefs, shown)           -> the GET /random query (shown = ids already picked in this tab, newest last)
//   activeFilters(prefs)            -> how many filters are set (for the "Filters (2)" label)
import type { Genre, RandomQuery } from '@/api/client'

export const PREFS_KEY = 'movie-prediction:surprise'
export const DECADES = [1960, 1970, 1980, 1990, 2000, 2010, 2020] as const
export const RUNTIMES = [90, 100, 120, 150] as const
export const MAX_EXCLUDE = 200 // the API's cap; older picks may come back after 200 spins

export type Source = 'all' | 'watchlist'
export type SurprisePrefs = {
  source: Source; genre: Genre | null; decade: number | null; language: string | null; maxRuntime: number | null
  gems: boolean
}
export const DEFAULTS: SurprisePrefs = { source: 'all', genre: null, decade: null, language: null, maxRuntime: null, gems: false }
export const NO_FILTERS = { genre: null, decade: null, language: null, maxRuntime: null } as const

const pickOf = <T,>(value: unknown, allowed: readonly T[]): T | null => allowed.includes(value as T) ? value as T : null

/** A genre is kept as any name: the menu shows only known ones, and the API refuses one it doesn't know. */
export function loadPrefs(): SurprisePrefs {
  let saved: Record<string, unknown> = {}
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(PREFS_KEY) ?? '{}')
    if (parsed && typeof parsed === 'object') saved = parsed as Record<string, unknown>
  } catch { /* blocked or broken storage: the defaults */ }
  return {
    source: saved.source === 'watchlist' ? 'watchlist' : 'all',
    genre: typeof saved.genre === 'string' && saved.genre ? saved.genre as Genre : null,
    decade: pickOf(saved.decade, DECADES),
    language: typeof saved.language === 'string' && /^[a-z]{2}$/.test(saved.language) ? saved.language : null,
    maxRuntime: pickOf(saved.maxRuntime, RUNTIMES),
    gems: saved.gems === true,
  }
}

export function savePrefs(prefs: SurprisePrefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
  } catch { /* not remembered: fine */ }
}

export function toQuery(prefs: SurprisePrefs, shown: number[]): RandomQuery {
  const exclude = shown.slice(-MAX_EXCLUDE).join(',')
  return {
    source: prefs.source, genre: prefs.genre ?? undefined, decade: prefs.decade ?? undefined,
    language: prefs.language ?? undefined, max_runtime: prefs.maxRuntime ?? undefined,
    gems: prefs.source === 'all' && prefs.gems ? true : undefined, exclude: exclude || undefined,
  }
}

export const activeFilters = (p: SurprisePrefs) => [p.genre, p.decade, p.language, p.maxRuntime].filter(v => v !== null).length
