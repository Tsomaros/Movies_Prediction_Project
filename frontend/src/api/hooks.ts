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
//   useCompare(body)                       -> POST /predict/compare as a query (the compare page), kept for the session
//   useSweep(body)                         -> POST /predict/sweep (the release-month sweep), kept for the session
//   useModelCard()                         -> GET /model-card, cached an hour
//   useCareer(id, role)                    -> the Career section's chart and track-record forecast, cached an hour
//   useCareerModel(id, role, genre, on)    -> the film model's films ("Something new" for one genre chip when genre
//                                             is set); a new chip keeps the last answer on screen until it arrives
//   useMovies(query) / useMovie(id)        -> browse and one film, cached an hour like the API says; a new page or
//                                             filter keeps the last results on screen until the new ones arrive
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  ApiError, api, type CareerRole, type CompareRequest, type MovieQuery, type NameKind, type PersonMatch, type PredictForm, type SweepRequest,
} from '@/api/client'
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

export function useCompare(body: CompareRequest | null) {
  return useQuery({
    queryKey: ['compare', body],
    queryFn: ({ signal }) => api.compare(body!, signal),
    enabled: body !== null,
    staleTime: Infinity,
    gcTime: HOUR,
    retry: false,
  })
}

export function useSweep(body: SweepRequest | null) {
  return useQuery({
    queryKey: ['sweep', body],
    queryFn: ({ signal }) => api.sweep(body!, signal),
    enabled: body !== null,
    staleTime: Infinity,
    gcTime: HOUR,
    retry: false,
  })
}

export function useModelCard() {
  return useQuery({ queryKey: ['model-card'], queryFn: ({ signal }) => api.getModelCard(signal), staleTime: HOUR })
}

export function useMovies(query: MovieQuery, enabled = true) {
  return useQuery({
    queryKey: ['movies', query],
    queryFn: ({ signal }) => api.listMovies(query, signal),
    enabled,
    staleTime: HOUR,
    placeholderData: keepPreviousData,
  })
}

export function usePerson(id: number | null) {
  return useQuery({
    queryKey: ['person', id],
    queryFn: ({ signal }) => api.getPerson(id!, signal),
    enabled: id !== null,
    staleTime: HOUR,
    retry: (count, error) => !(error instanceof ApiError && error.kind === 'not_found') && count < 1,
  })
}

export function useCareer(id: number, role: CareerRole) {
  return useQuery({
    queryKey: ['career', id, role],
    queryFn: ({ signal }) => api.getCareer(id, role, signal),
    staleTime: HOUR,
    retry: (count, error) => !(error instanceof ApiError && error.kind === 'not_found') && count < 1,
  })
}

/** Each genre is its own query, so a slow answer for an earlier chip lands in its own cache entry and never
 *  replaces the chip chosen since. */
export function useCareerModel(id: number, role: CareerRole, genre: number | null, enabled: boolean) {
  return useQuery({
    queryKey: ['career-model', id, role, genre],
    queryFn: ({ signal }) => api.getCareerModel(id, role, genre, signal),
    enabled,
    staleTime: HOUR,
    placeholderData: keepPreviousData,
    retry: (count, error) => !(error instanceof ApiError && error.kind === 'not_found') && count < 1,
  })
}

export type RowPerson = PersonMatch & { role: 'actor' | 'director' }

/** Actors and directors for browse search's people row (Day 14.7): both searches merged by id (someone in both
 *  appears once, in the role with more films), most films first, at most `limit`; only for 2+ typed characters
 *  (q is already debounced). */
export function usePeopleRow(q: string, limit: number) {
  const text = q.trim()
  return useQuery({
    queryKey: ['people-row', text, limit],
    queryFn: async ({ signal }): Promise<RowPerson[]> => {
      const [actors, directors] = await Promise.all((['actor', 'director'] as const).map(role =>
        api.searchPeople(text, limit, role, signal).then(hits => hits.map(h => ({ ...h, role })))))
      const best = new Map<number, RowPerson>()
      for (const p of [...actors, ...directors]) {
        const seen = best.get(p.id)
        if (!seen || p.n_films > seen.n_films) best.set(p.id, p)
      }
      return [...best.values()].sort((a, b) => b.n_films - a.n_films || a.name.localeCompare(b.name)).slice(0, limit)
    },
    enabled: text.length >= 2,
    staleTime: HOUR,
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
