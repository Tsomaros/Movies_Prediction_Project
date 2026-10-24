// The demo account's session as TanStack Query state. The cookie is httpOnly, so the app only knows who is
// logged in by asking GET /auth/me (once a visit; logging in or out updates the answer directly).
//
//   ME_KEY                -> ['me']: the session; every user query lives under it (['me', 'status', ids], ...)
//   useMe()               -> the query plus `user` (null when logged out, also when accounts are off: a 503)
//   useDemoLogin()        -> POST /auth/demo (the one-click button)
//   useLogin()            -> POST /auth/login with a username and password
//   useLogout()           -> POST /auth/logout; every user query is dropped, so nothing private stays on screen
//   useSessionEnded()     -> the same clean-up after a 401 (logged out in another tab, or the session expired)
//   isMeKey(key)          -> true for a user query (under ['me'], not the session itself)
import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'

import { api, type Me } from '@/api/client'

export const ME_KEY = ['me'] as const
export const isMeKey = (key: QueryKey) => key[0] === 'me' && key.length > 1

export function useMe() {
  const query = useQuery({ queryKey: ME_KEY, queryFn: ({ signal }) => api.me(signal), staleTime: Infinity, retry: false })
  return { ...query, user: query.data?.user ?? null }
}

function useLoggedIn() {
  const client = useQueryClient()
  return (me: Me) => {
    client.removeQueries({ predicate: q => isMeKey(q.queryKey) }) // another account's leftovers, if any
    client.setQueryData(ME_KEY, me)
  }
}

export function useDemoLogin() {
  const loggedIn = useLoggedIn()
  return useMutation({ mutationFn: () => api.demoLogin(), onSuccess: loggedIn })
}

export function useLogin() {
  const loggedIn = useLoggedIn()
  return useMutation({
    mutationFn: (body: { username: string; password: string }) => api.login(body),
    onSuccess: loggedIn,
  })
}

export function useSessionEnded() {
  const client = useQueryClient()
  return () => {
    client.setQueryData<Me>(ME_KEY, { user: null })
    client.removeQueries({ predicate: q => isMeKey(q.queryKey) })
  }
}

export function useLogout() {
  const ended = useSessionEnded()
  return useMutation({ mutationFn: () => api.logout(), onSuccess: ended })
}
