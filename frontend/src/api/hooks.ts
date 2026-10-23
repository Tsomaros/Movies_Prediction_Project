// TanStack Query hooks over the client: one place for cache times, debouncing and error toasts.
//
//   useMetaOptions()                       -> every dropdown value and limit (cached an hour, like the API says)
//   useNameSearch(kind, q)                 -> autocomplete, 250 ms after the last keystroke, from 1 character
//   usePeopleSearch(role, q), useCompanySearch(q), useCollectionSearch(q)   -> the same, per field
//   usePredict()                           -> POST /predict; 429, network and server errors toast by themselves,
//                                             a 422 is left to the form (applyFieldErrors in errors.ts); the
//                                             answer is also cached under predictionKey(form)
//   usePrediction(form)                    -> the same answer as a query (the results page): from that cache when
//                                             the form page just asked, else one request; errors are the page's
//   useModelCard()                         -> GET /model-card, cached an hour
//   useMovies(query) / useMovie(id)        -> browse and one film, cached an hour like the API says; a new page or
//                                             filter keeps the last results on screen until the new ones arrive
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, type MovieQuery, type NameKind, type PredictForm } from '@/api/client'
import { notifyError } from '@/api/errors'
import { useDebounced } from '@/lib/useDebounced'

export const DEBOUNCE_MS = 250
const HOUR = 60 * 60 * 1000

export function useMetaOptions() {
  return useQuery({
    queryKey: ['meta', 'options'],
    queryFn: ({ signal }) => api.getOptions(signal),
    staleTime: HOUR,
  })
}

export function useNameSearch(kind: NameKind, q: string) {
  const term = useDebounced(q.trim(), DEBOUNCE_MS)
  const query = useQuery({
    queryKey: ['names', kind, term.toLowerCase()],
    queryFn: ({ signal }) => api.searchNames(kind, term, signal),
    enabled: term.length >= 1,
    staleTime: HOUR,
  })
  return { ...query, term, typing: q.trim() !== term }
}

export const usePeopleSearch = (role: 'director' | 'actor', q: string) => useNameSearch(role, q)
export const useCompanySearch = (q: string) => useNameSearch('company', q)
export const useCollectionSearch = (q: string) => useNameSearch('franchise', q)

export const predictionKey = (form: PredictForm | null) => ['predict', form] as const

export function usePredict() {
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: (form: PredictForm) => api.predict(form),
    onSuccess: (data, form) => client.setQueryData(predictionKey(form), data),
    onError: (error, form) => notifyError(error, () => mutation.mutate(form)),
  })
  return mutation
}

/** A prediction never changes for the same form and model, so it is kept for the session (and never retried:
 *  a 422 or 429 won't go away by asking again at once). */
export function usePrediction(form: PredictForm | null) {
  return useQuery({
    queryKey: predictionKey(form),
    queryFn: ({ signal }) => api.predict(form!, signal),
    enabled: form !== null,
    staleTime: Infinity,
    gcTime: HOUR,
    retry: false,
  })
}

export function useModelCard() {
  return useQuery({ queryKey: ['model-card'], queryFn: ({ signal }) => api.getModelCard(signal), staleTime: HOUR })
}

export function useMovies(query: MovieQuery) {
  return useQuery({
    queryKey: ['movies', query],
    queryFn: ({ signal }) => api.listMovies(query, signal),
    staleTime: HOUR,
    placeholderData: keepPreviousData,
  })
}

export function useMovie(id: number | null) {
  return useQuery({
    queryKey: ['movie', id],
    queryFn: ({ signal }) => api.getMovie(id!, signal),
    enabled: id !== null,
    staleTime: HOUR,
    retry: (count, error) => !(error instanceof ApiError && error.kind === 'not_found') && count < 1,
  })
}
