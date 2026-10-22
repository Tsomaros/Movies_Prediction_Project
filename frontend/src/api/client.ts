// The one typed client for the backend (/api/v1, proxied by Vite in dev and by nginx in docker compose).
//
//   getOptions(), searchNames(kind, q), predict(form)   -> typed bodies from schema.d.ts (npm run gen:api)
//   ApiError                                             -> every failure, with a `kind` the UI can act on:
//     validation   422, `fieldErrors` keyed by the API's dotted paths ("actors.2", "budget")
//     rate_limited 429, `retryAfter` seconds from the Retry-After header
//     not_found    404
//     network      the request never got an answer (offline, server down, CORS)
//     server       any other status, or a body that isn't JSON
import type { components } from '@/api/schema'

type Schemas = components['schemas']
export type Options = Schemas['Options']
export type FieldSpec = Schemas['FieldSpec']
export type Match = Schemas['Match']
export type PredictForm = Schemas['PredictForm']
export type Prediction = Schemas['Prediction']
export type FieldErrors = Schemas['FieldErrors']

export const API_BASE = '/api/v1'

export type ApiErrorKind = 'validation' | 'rate_limited' | 'not_found' | 'network' | 'server'

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
  { method?: 'GET' | 'POST'; query?: Query; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
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
  if (status === 404) throw new ApiError('not_found', message, { status })
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
}
