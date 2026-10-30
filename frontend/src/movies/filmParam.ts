// The quick-view modal of a live film is the `?film=<tmdb id>` parameter of whatever page opened it, so a link
// shows the same film and Back closes it.
//
//   FILM_PARAM            -> "film"
//   useOpenFilm()         -> (tmdbId) => adds ?film= to the current address (a new history entry)
//   useCloseFilm()        -> () => removes ?film= (replacing the entry, so Back does not reopen it)
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

export const FILM_PARAM = 'film'

export function useOpenFilm() {
  const [, setParams] = useSearchParams()
  return useCallback((tmdbId: number) => setParams(p => {
    const next = new URLSearchParams(p)
    next.set(FILM_PARAM, String(tmdbId))
    return next
  }, { preventScrollReset: true }), [setParams])
}

export function useCloseFilm() {
  const [, setParams] = useSearchParams()
  return useCallback(() => setParams(p => {
    const next = new URLSearchParams(p)
    next.delete(FILM_PARAM)
    return next
  }, { replace: true, preventScrollReset: true }), [setParams])
}
