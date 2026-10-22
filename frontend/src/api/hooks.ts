// TanStack Query hooks over the client: one place for cache times, debouncing and error toasts.
//
//   useMetaOptions()                       -> every dropdown value and limit (cached an hour, like the API says)
//   useNameSearch(kind, q)                 -> autocomplete, 250 ms after the last keystroke, from 1 character
//   usePeopleSearch(role, q), useCompanySearch(q), useCollectionSearch(q)   -> the same, per field
//   usePredict()                           -> POST /predict; 429, network and server errors toast by themselves,
//                                             a 422 is left to the form (applyFieldErrors in errors.ts)
import { useMutation, useQuery } from '@tanstack/react-query'

import { api, type NameKind, type PredictForm } from '@/api/client'
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

export function usePredict() {
  const mutation = useMutation({
    mutationFn: (form: PredictForm) => api.predict(form),
    onError: (error, form) => notifyError(error, () => mutation.mutate(form)),
  })
  return mutation
}
