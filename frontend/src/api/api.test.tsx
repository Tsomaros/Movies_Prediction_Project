import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { api, ApiError, type PredictForm } from '@/api/client'
import { applyFieldErrors, notifyError, RATE_LIMITED } from '@/api/errors'
import { DEBOUNCE_MS, useMetaOptions, useNameSearch, usePredict } from '@/api/hooks'
import { mockFetch } from '@/test/fetch'

vi.mock('sonner', () => ({ toast: { error: vi.fn(), warning: vi.fn() } }))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const FIELD_ERRORS = { detail: 'Some fields need fixing', errors: { 'actors.2': 'unknown field', runtime: 'must be between 40 and 300' } }

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(() => null, e => e)
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

describe('client', () => {
  test('a 200 returns the parsed body, with the query string encoded', async () => {
    const { calls } = mockFetch({ '/api/v1/people': { body: [{ id: 45400, name: 'Greta Gerwig', n_films: 4 }] } })
    expect(await api.searchNames('director', 'greta g')).toEqual([{ id: 45400, name: 'Greta Gerwig', n_films: 4 }])
    expect(calls[0].url.search).toBe('?role=director&q=greta+g')
  })

  test('each name kind goes to its endpoint', async () => {
    const { calls } = mockFetch({ '/api/v1/people': { body: [] }, '/api/v1/companies': { body: [] }, '/api/v1/collections': { body: [] } })
    for (const kind of ['actor', 'company', 'franchise'] as const) await api.searchNames(kind, 'a')
    expect(calls.map(c => `${c.url.pathname}${c.url.search}`)).toEqual(
      ['/api/v1/people?role=actor&q=a', '/api/v1/companies?q=a', '/api/v1/collections?q=a'])
  })

  test('predict posts the form as JSON', async () => {
    const { calls } = mockFetch({ '/api/v1/predict': { body: { cached: false } } })
    await api.predict({ runtime: 100 } as PredictForm)
    expect(calls[0].init?.method).toBe('POST')
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ runtime: 100 })
    expect(new Headers(calls[0].init?.headers).get('Content-Type')).toBe('application/json')
  })

  test('a 422 becomes a validation error with the field messages', async () => {
    mockFetch({ '/api/v1/predict': { status: 422, body: FIELD_ERRORS } })
    const error = await failure(api.predict({} as PredictForm))
    expect([error.kind, error.status, error.message]).toEqual(['validation', 422, 'Some fields need fixing'])
    expect(error.fieldErrors).toEqual(FIELD_ERRORS.errors)
  })

  test('a 429 becomes rate_limited with Retry-After', async () => {
    mockFetch({ '/api/v1/predict': { status: 429, body: { detail: 'Too many' }, headers: { 'Retry-After': '42' } } })
    const error = await failure(api.predict({} as PredictForm))
    expect([error.kind, error.retryAfter]).toEqual(['rate_limited', 42])
  })

  test.each([
    [404, 'not_found'],
    [500, 'server'],
    [502, 'server'],
  ])('a %i becomes %s', async (status, kind) => {
    mockFetch({ '/api/v1/meta/options': { status, body: { detail: 'x' } } })
    expect((await failure(api.getOptions())).kind).toBe(kind)
  })

  test('a 200 that is not JSON (a proxy error page) is a server error', async () => {
    mockFetch({ '/api/v1/meta/options': { body: '<html>Bad gateway</html>' } })
    expect((await failure(api.getOptions())).kind).toBe('server')
  })

  test('no answer at all is a network error', async () => {
    mockFetch({ '/api/v1/meta/options': new TypeError('Failed to fetch') })
    const error = await failure(api.getOptions())
    expect(error.kind).toBe('network')
    expect(error.message).toMatch(/Can't reach the server/)
  })

  test('a cancelled request stays a cancellation, not a network error', async () => {
    const controller = new AbortController()
    controller.abort()
    mockFetch({ '/api/v1/people': new DOMException('aborted', 'AbortError') })
    const error = await api.searchNames('actor', 'a', controller.signal).then(() => null, e => e)
    expect(error).not.toBeInstanceOf(ApiError)
  })
})

describe('errors', () => {
  test('a 422 lands on the form fields, the first one focused, and unknown paths come back', () => {
    const setError = vi.fn()
    const error = new ApiError('validation', 'Some fields need fixing', {
      fieldErrors: { 'actors.2': 'must be a name or an id', runtime: 'too long', 'variants.0.x': 'odd' } })
    const leftover = applyFieldErrors(error, setError, path => (path.startsWith('variants') ? null : path))
    expect(setError.mock.calls).toEqual([
      ['actors.2', { type: 'server', message: 'must be a name or an id' }, { shouldFocus: true }],
      ['runtime', { type: 'server', message: 'too long' }, { shouldFocus: false }],
    ])
    expect(leftover).toEqual(['variants.0.x: odd'])
  })

  test('a 422 without field messages shows its detail', () => {
    expect(applyFieldErrors(new ApiError('validation', 'Some fields need fixing'), vi.fn())).toEqual(['Some fields need fixing'])
  })

  test('429 warns "try again in a minute"; network and server errors offer a retry', () => {
    const retry = vi.fn()
    expect(notifyError(new ApiError('rate_limited', 'x', { retryAfter: 30 }), retry)).toBe(true)
    expect(toast.warning).toHaveBeenCalledWith(RATE_LIMITED, { id: 'rate-limited' })
    notifyError(new ApiError('network', "Can't reach the server."), retry)
    const [message, options] = vi.mocked(toast.error).mock.calls[0]
    expect(message).toBe("Can't reach the server.")
    expect((options as { action: { label: string } }).action.label).toBe('Retry')
  })

  test('a long Retry-After says how many minutes', () => {
    notifyError(new ApiError('rate_limited', 'x', { retryAfter: 150 }))
    expect(toast.warning).toHaveBeenCalledWith('Too many predictions – try again in 3 minutes.', { id: 'rate-limited' })
  })

  test('a 422 or a plain error is left to the caller', () => {
    expect(notifyError(new ApiError('validation', 'x'))).toBe(false)
    expect(notifyError(new Error('boom'))).toBe(false)
    expect(toast.error).not.toHaveBeenCalled()
  })
})

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('hooks', () => {
  test('useMetaOptions loads the options once', async () => {
    const { fetch } = mockFetch({ '/api/v1/meta/options': { body: { genres: ['Drama'] } } })
    const { result } = renderHook(() => useMetaOptions(), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual({ genres: ['Drama'] }))
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  test('autocomplete waits for typing to stop, and asks once for the last text', async () => {
    const { calls } = mockFetch({ '/api/v1/people': url => ({ body: [{ id: 1, name: url.searchParams.get('q'), n_films: 3 }] }) })
    const { result, rerender } = renderHook(({ q }) => useNameSearch('actor', q), { wrapper, initialProps: { q: '' } })
    for (const q of ['t', 'to', 'tom', 'tom h']) rerender({ q })
    expect(result.current.typing).toBe(true)
    expect(calls).toHaveLength(0)
    await waitFor(() => expect(result.current.data?.[0].name).toBe('tom h'), { timeout: DEBOUNCE_MS * 4 })
    expect(calls.map(c => c.url.searchParams.get('q'))).toEqual(['tom h'])
    expect(result.current.typing).toBe(false)
  })

  test('autocomplete asks nothing for empty or blank text', async () => {
    const { calls } = mockFetch({})
    const { result } = renderHook(() => useNameSearch('company', '   '), { wrapper })
    await new Promise(r => setTimeout(r, DEBOUNCE_MS + 50))
    expect(calls).toHaveLength(0)
    expect(result.current.fetchStatus).toBe('idle')
  })

  test('usePredict toasts a 429 by itself and leaves a 422 to the form', async () => {
    let status = 429
    mockFetch({ '/api/v1/predict': () => ({ status, body: status === 422 ? FIELD_ERRORS : { detail: 'x' } }) })
    const { result } = renderHook(() => usePredict(), { wrapper })
    await act(() => result.current.mutateAsync({} as PredictForm).catch(() => {}))
    expect(toast.warning).toHaveBeenCalledTimes(1)
    status = 422
    await act(() => result.current.mutateAsync({} as PredictForm).catch(() => {}))
    await waitFor(() => expect((result.current.error as ApiError).kind).toBe('validation'))
    expect(toast.warning).toHaveBeenCalledTimes(1)
    expect(toast.error).not.toHaveBeenCalled()
  })
})
