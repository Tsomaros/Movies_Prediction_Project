// Shows the quick view of a live film when the address has ?film=<tmdb id> (V1.2). It lives in the Layout, so a card
// on any page, a header search result or a shared link all open the same modal. The live lists are asked for only
// while the parameter is there; an id that is not in them (or a failed request) removes the parameter again.
import { lazy, Suspense, useEffect } from 'react'
import { useSearchParams } from 'react-router'

import { useNewAndUpcoming } from '@/api/hooks'
import { FILM_PARAM, useCloseFilm } from '@/movies/filmParam'

const QuickViewModal = lazy(() => import('@/movies/QuickViewModal'))

export function LiveFilmHost() {
  const [params] = useSearchParams()
  const id = Number(params.get(FILM_PARAM))
  const wanted = params.has(FILM_PARAM)
  const live = useNewAndUpcoming(wanted)
  const close = useCloseFilm()
  const film = Number.isInteger(id) ? [...(live.data?.new ?? []), ...(live.data?.upcoming ?? [])].find(f => f.tmdb_id === id) : undefined
  const unknown = wanted && (!Number.isInteger(id) || live.isError || (live.isSuccess && !film))
  useEffect(() => { if (unknown) close() }, [unknown, close])
  if (!wanted || !film) return null
  return <Suspense fallback={null}><QuickViewModal film={film} onClose={close} /></Suspense>
}
