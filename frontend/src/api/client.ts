// The one typed client for the backend (/api/v1, proxied by Vite in dev and by nginx in docker compose).
//
//   getOptions(), searchNames(kind, q), predict(form), compare(body), sweep(body), getModelCard(),
//   listMovies(query), getMovie(id)                     -> typed bodies from schema.d.ts (npm run gen:api)
//   me(), demoLogin(), login(body), logout()             -> the demo account's session (an httpOnly cookie, same origin)
//   myMovies(query), statuses(ids), setEntry(id, body), removeEntry(id),
//   filmNotes(id), addNote(id, body), allNotes(page), editNote(id, body), deleteNote(id)   -> lists and notes
//   random(query)                                        -> "Surprise me": one random film, or why there is none
//   ApiError                                             -> every failure, with a `kind` the UI can act on:
//     validation   422, `fieldErrors` keyed by the API's dotted paths ("actors.2", "budget")
//     rate_limited 429, `retryAfter` seconds from the Retry-After header
//     unauthorized 401 (not logged in, or the session ended)
//     not_found    404
//     conflict     409 (a list or the notes are full; the message says so)
//     network      the request never got an answer (offline, server down, CORS)
//     server       any other status, or a body that isn't JSON
import type { components, operations } from '@/api/schema'

type Schemas = components['schemas']
export type Options = Schemas['Options']
export type FieldSpec = Schemas['FieldSpec']
export type Match = Schemas['Match']
export type PredictForm = Schemas['PredictForm']
export type Prediction = Schemas['Prediction']
export type FormChanges = Schemas['FormChanges']
export type CompareRequest = Schemas['CompareRequest']
export type CompareResponse = Schemas['CompareResponse']
export type SweepRequest = Schemas['SweepRequest']
export type SweepResponse = Schemas['SweepResponse']
export type FieldErrors = Schemas['FieldErrors']
export type Comparable = Schemas['Comparable']
export type Driver = Schemas['Driver']
export type ModelCard = Schemas['ModelCard']
export type MovieSummary = Schemas['MovieSummary']
export type MovieList = Schemas['MovieList']
export type MovieDetail = Schemas['MovieDetail']
export type User = Schemas['User']
export type Me = Schemas['Me']
export type Status = Schemas['EntryRequest']['status']
export type EntryRequest = Schemas['EntryRequest']
export type Entry = Schemas['Entry']
export type MyMovieList = Schemas['MyMovieList']
export type MyMovie = Schemas['MyMovie']
export type Counts = Schemas['Counts']
export type MySort = NonNullable<NonNullable<operations['my_movies_api_v1_me_movies_get']['parameters']['query']>['sort']>
export type Note = Schemas['Note']
export type NotePage = Schemas['NotePage']
export type RandomPick = Schemas['RandomPick']
export type RandomMovie = Schemas['RandomMovie']
type RandomQueryAll = NonNullable<operations['random_film_api_v1_random_get']['parameters']['query']>
export type RandomQuery = { [K in keyof RandomQueryAll]?: NonNullable<RandomQueryAll[K]> }
/** GET /movies's query (every filter optional), from the generated schema; null is left out. */
type ListQuery = NonNullable<operations['list_movies_api_v1_movies_get']['parameters']['query']>
export type MovieQuery = { [K in keyof ListQuery]?: NonNullable<ListQuery[K]> }
export type Sort = NonNullable<MovieQuery['sort']>
export type Genre = NonNullable<MovieQuery['genre']>

export const API_BASE = '/api/v1'

export type ApiErrorKind = 'validation' | 'rate_limited' | 'unauthorized' | 'not_found' | 'conflict' | 'network' | 'server'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly fieldErrors: Record<string, string>
  readonly retryAfter: number | null

  constructor(kind: ApiErrorKind, message: string,
    { status = null, fieldErrors = {}, retryAfter = null }:
    { status?: number | null; fieldErrors?: Record<string, string>; retryAfter?: number | null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.fieldErrors = fieldErrors
    this.retryAfter = retryAfter
  }
}

type Query = Record<string, string | number | undefined>

async function request<T>(path: string, { method = 'GET', query, body, signal }:
  { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; query?: Query; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined) params.set(k, String(v))
  const url = `${API_BASE}${path}${params.size ? `?${params}` : ''}`

  let response: Response
  try {
    response = await fetch(url, {
      method, signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    if (signal?.aborted) throw error // a cancelled query (TanStack Query aborts stale autocomplete requests)
    throw new ApiError('network', "Can't reach the server. Check your connection and try again.")
  }

  if (response.status === 204) return undefined as T // logout, removing a film or a note: no body
  const data: unknown = await response.json().catch(() => undefined)
  if (response.ok && data !== undefined) return data as T
  const detail = (data as { detail?: unknown } | undefined)?.detail
  const message = typeof detail === 'string' ? detail : `The server answered ${response.status}.`
  const status = response.status
  if (status === 422) {
    const errors = (data as Partial<FieldErrors> | undefined)?.errors ?? {}
    throw new ApiError('validation', message, { status, fieldErrors: errors })
  }
  if (status === 429) {
    const seconds = Number(response.headers.get('Retry-After'))
    throw new ApiError('rate_limited', message, { status, retryAfter: Number.isFinite(seconds) && seconds > 0 ? seconds : null })
  }
  if (status === 401) throw new ApiError('unauthorized', message, { status })
  if (status === 404) throw new ApiError('not_found', message, { status })
  if (status === 409) throw new ApiError('conflict', message, { status })
  throw new ApiError('server', 'Something went wrong on our side. Please try again.', { status })
}

export type NameKind = 'director' | 'actor' | 'company' | 'franchise'

const NAME_ENDPOINTS: Record<NameKind, { path: string; query?: Query }> = {
  director: { path: '/people', query: { role: 'director' } },
  actor: { path: '/people', query: { role: 'actor' } },
  company: { path: '/companies' },
  franchise: { path: '/collections' },
}

export const api = {
  getOptions: (signal?: AbortSignal) => request<Options>('/meta/options', { signal }),
  searchNames: (kind: NameKind, q: string, signal?: AbortSignal) => {
    const { path, query } = NAME_ENDPOINTS[kind]
    return request<Match[]>(path, { query: { ...query, q }, signal })
  },
  predict: (form: PredictForm, signal?: AbortSignal) =>
    request<Prediction>('/predict', { method: 'POST', body: form, signal }),
  compare: (body: CompareRequest, signal?: AbortSignal) =>
    request<CompareResponse>('/predict/compare', { method: 'POST', body, signal }),
  sweep: (body: SweepRequest, signal?: AbortSignal) =>
    request<SweepResponse>('/predict/sweep', { method: 'POST', body, signal }),
  getModelCard: (signal?: AbortSignal) => request<ModelCard>('/model-card', { signal }),
  listMovies: (query: MovieQuery, signal?: AbortSignal) => request<MovieList>('/movies', { query, signal }),
  getMovie: (id: number, signal?: AbortSignal) => request<MovieDetail>(`/movies/${id}`, { signal }),

  me: (signal?: AbortSignal) => request<Me>('/auth/me', { signal }),
  demoLogin: () => request<Me>('/auth/demo', { method: 'POST' }),
  login: (body: { username: string; password: string }) => request<Me>('/auth/login', { method: 'POST', body }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  myMovies: (query: { status: Status; sort: MySort; page: number }, signal?: AbortSignal) =>
    request<MyMovieList>('/me/movies', { query, signal }),
  statuses: (ids: number[], signal?: AbortSignal) =>
    request<Schemas['StatusList']>('/me/movies/status', { query: { ids: ids.join(',') }, signal }),
  setEntry: (id: number, body: EntryRequest) => request<Entry>(`/me/movies/${id}`, { method: 'PUT', body }),
  removeEntry: (id: number) => request<void>(`/me/movies/${id}`, { method: 'DELETE' }),
  filmNotes: (id: number, signal?: AbortSignal) => request<Schemas['NoteList']>(`/me/movies/${id}/notes`, { signal }),
  addNote: (id: number, body: string) => request<Note>(`/me/movies/${id}/notes`, { method: 'POST', body: { body } }),
  allNotes: (page: number, signal?: AbortSignal) => request<NotePage>('/me/notes', { query: { page }, signal }),
  editNote: (id: number, body: string) => request<Note>(`/me/notes/${id}`, { method: 'PATCH', body: { body } }),
  deleteNote: (id: number) => request<void>(`/me/notes/${id}`, { method: 'DELETE' }),
  random: ({ gems, ...query }: RandomQuery, signal?: AbortSignal) =>
    request<RandomPick>('/random', { query: { ...query, gems: gems ? 'true' : undefined }, signal }),
}
