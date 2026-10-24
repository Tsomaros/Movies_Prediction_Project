// TanStack Query hooks for the logged-in user's lists and notes. Every key is under ['me'], so logging out drops
// them all (src/auth/session.ts), and every write refreshes them all once it is done.
//
//   useStatuses(ids)          -> Map film id -> list entry, for up to 48 films (one browse page) in one request
//   useSetEntry()             -> PUT (or, with body null, DELETE) /me/movies/{id}; optimistic: the badges and
//                                buttons change at once and roll back with a toast if the server says no
//   useListChange()           -> change(id, body, previous): the same behind a login (useRequireLogin), plus
//                                "Rating removed · Undo" when a rated film leaves the watched list
//   useMyMovies(query)        -> one tab of /my-movies, with every tab's count
//   useFilmNotes(id), useAllNotes(page)
//   todayIso(), noteDate(iso)  -> today as "2026-10-24" (the visitor's time zone); "24 Oct 2026"
//   useAddNote(id), useEditNote(), useDeleteNote()   -> notes; deleting is optimistic and offers Undo (it adds
//                                the note again, as the newest)
import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useMemo } from 'react'
import { toast } from 'sonner'

import { ApiError, api, type Entry, type EntryRequest, type MySort, type Note, type Status } from '@/api/client'
import { notifyError } from '@/api/errors'
import { useRequireLogin } from '@/auth/requireLogin'
import { isMeKey, useMe, useSessionEnded } from '@/auth/session'

type StatusList = { items: Entry[] }
type NoteList = { items: Note[] }

export const statusKey = (ids: number[]) => ['me', 'status', ids] as const
export const notesKey = (id: number) => ['me', 'notes', id] as const
export const UNDO_MS = 8000 // an Undo toast stays this long (sonner's default 4 s is short for reading and reaching it)

/** Today in the visitor's time zone, as the API's date strings ("2026-10-24"). */
export function todayIso(now = new Date()): string {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

export function noteDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function useFailed() {
  const ended = useSessionEnded()
  return (error: Error) => {
    if (error instanceof ApiError && error.kind === 'unauthorized') ended()
    if (!notifyError(error)) toast.error(error.message)
  }
}

function useRefreshMine() {
  const client = useQueryClient()
  return () => client.invalidateQueries({ predicate: q => isMeKey(q.queryKey) })
}

export function useStatuses(ids: number[]) {
  const { user } = useMe()
  const query = useQuery({
    queryKey: statusKey(ids),
    queryFn: ({ signal }) => api.statuses(ids, signal),
    enabled: user !== null && ids.length > 0,
    staleTime: 5 * 60 * 1000,
  })
  return useMemo(() => new Map((query.data?.items ?? []).map(e => [e.movie_id, e])), [query.data])
}

/** The entry the server will make of `body` (watched today unless dated; the watchlist has no date or rating). */
function guess(id: number, body: EntryRequest, old: Entry | undefined): Entry {
  const now = new Date().toISOString()
  const watched = body.status === 'watched'
  return {
    movie_id: id, status: body.status,
    watched_on: watched ? body.watched_on ?? (old?.status === 'watched' ? old.watched_on : null) ?? todayIso() : null,
    rating: watched ? ('rating' in body ? body.rating ?? null : old?.status === 'watched' ? old.rating : null) : null,
    added_at: old && old.status === body.status ? old.added_at : now, updated_at: now,
  }
}

export function useSetEntry() {
  const client = useQueryClient()
  const failed = useFailed()
  const refresh = useRefreshMine()
  return useMutation({
    scope: { id: 'me-lists' }, // one write at a time, in click order: the last click is what the server keeps
    mutationFn: async ({ id, body }: { id: number; body: EntryRequest | null }): Promise<Entry | null> =>
      body ? api.setEntry(id, body) : api.removeEntry(id).then(() => null),
    onMutate: async ({ id, body }) => {
      await client.cancelQueries({ queryKey: ['me', 'status'] })
      const snapshot = client.getQueriesData<StatusList>({ queryKey: ['me', 'status'] })
      for (const [key, data] of snapshot) {
        if (!data || !(key[2] as number[]).includes(id)) continue
        const old = data.items.find(e => e.movie_id === id)
        const items = data.items.filter(e => e.movie_id !== id)
        client.setQueryData<StatusList>(key, { items: body ? [...items, guess(id, body, old)] : items })
      }
      return { snapshot }
    },
    onError: (error, _vars, context) => {
      context?.snapshot.forEach(([key, data]: [QueryKey, StatusList | undefined]) => client.setQueryData(key, data))
      failed(error)
    },
    onSettled: refresh,
  })
}

export function useListChange() {
  const set = useSetEntry()
  const requireLogin = useRequireLogin()
  return (id: number, body: EntryRequest | null, previous?: Entry) => requireLogin(() => {
    set.mutate({ id, body })
    if (previous?.status === 'watched' && previous.rating && body?.status !== 'watched') {
      const restore = { status: 'watched' as const, watched_on: previous.watched_on, rating: previous.rating }
      toast('Rating removed', { duration: UNDO_MS, action: { label: 'Undo', onClick: () => set.mutate({ id, body: restore }) } })
    }
  })
}

export function useMyMovies(query: { status: Status; sort: MySort; page: number }, enabled: boolean) {
  return useQuery({
    queryKey: ['me', 'movies', query],
    queryFn: ({ signal }) => api.myMovies(query, signal),
    enabled,
    placeholderData: keepPreviousData,
  })
}

export function useAllNotes(page: number, enabled: boolean) {
  return useQuery({
    queryKey: ['me', 'all-notes', page],
    queryFn: ({ signal }) => api.allNotes(page, signal),
    enabled,
    placeholderData: keepPreviousData,
  })
}

export function useFilmNotes(id: number) {
  const { user } = useMe()
  return useQuery({ queryKey: notesKey(id), queryFn: ({ signal }) => api.filmNotes(id, signal), enabled: user !== null })
}

export function useAddNote(id: number) {
  const failed = useFailed()
  const refresh = useRefreshMine()
  return useMutation({ mutationFn: (body: string) => api.addNote(id, body), onError: failed, onSettled: refresh })
}

export function useEditNote() {
  const failed = useFailed()
  const refresh = useRefreshMine()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) => api.editNote(id, body),
    onError: failed,
    onSettled: refresh,
  })
}

export function useDeleteNote(movieId: number) {
  const client = useQueryClient()
  const failed = useFailed()
  const refresh = useRefreshMine()
  return useMutation({
    mutationFn: (note: Note) => api.deleteNote(note.id),
    onMutate: async note => {
      await client.cancelQueries({ queryKey: notesKey(movieId) })
      const before = client.getQueryData<NoteList>(notesKey(movieId))
      if (before) client.setQueryData<NoteList>(notesKey(movieId), { items: before.items.filter(n => n.id !== note.id) })
      return { before }
    },
    onError: (error, _note, context) => {
      if (context?.before) client.setQueryData(notesKey(movieId), context.before)
      failed(error)
    },
    onSettled: refresh,
  })
}
