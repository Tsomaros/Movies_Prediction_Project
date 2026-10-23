// Day 13's edge cases, one place: a slow (waking) server, the API down, too many requests, links cut or edited by
// hand. Movie 404s and the 429 on the results page are in movies.test.tsx and result.test.tsx.
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { MovieList, Options } from '@/api/client'
import { SlowNotice, WAKING_UP } from '@/app/SlowNotice'
import { EXAMPLES } from '@/form/examples'
import { encodeForm, toBase64Url } from '@/form/persist'
import { browseResets } from '@/movies/browse'
import { mockFetch } from '@/test/fetch'
import moviesJson from '@/test/movies.json'
import optionsJson from '@/test/options.json'
import predictionsJson from '@/test/predictions.json'
import { renderApp } from '@/test/render'

const options = optionsJson as Options
const drama = EXAMPLES.find(e => e.key === 'small_drama')!

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('a server waking up', () => {
  test('after 3 s of waiting the notice explains, and it goes when the answer comes', () => {
    vi.useFakeTimers()
    const { rerender } = render(<SlowNotice pending />)
    act(() => vi.advanceTimersByTime(2900))
    expect(screen.queryByTestId('slow-notice')).toBeNull()
    act(() => vi.advanceTimersByTime(200))
    expect(screen.getByRole('status')).toHaveTextContent(WAKING_UP)
    rerender(<SlowNotice pending={false} />)
    expect(screen.queryByTestId('slow-notice')).toBeNull()
  })

  test('the results page shows it while the prediction is slow (a real 3 s wait)', async () => {
    vi.stubGlobal('fetch', vi.fn((input: string) => String(input).endsWith('/predict')
      ? new Promise<Response>(() => {}) : Promise.resolve(new Response('{}', { status: 503 }))))
    renderApp(`/predict/result?f=${encodeForm(drama.form)}`)
    await screen.findByText('Running the models…')
    expect(screen.queryByTestId('slow-notice')).toBeNull()
    expect(await screen.findByTestId('slow-notice', {}, { timeout: 4000 })).toHaveTextContent('Waking up the server')
  }, 6000)
})

describe('the API down', () => {
  test('a failed prediction keeps the form as it was, with a retry', async () => {
    mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/predict': new TypeError('Failed to fetch') })
    const { router } = renderApp(`/predict?f=${encodeForm(drama.form)}`)
    await userEvent.click(await screen.findByRole('button', { name: /^Predict/ }))
    expect(await screen.findByText("Can't reach the server. Check your connection and try again.")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/predict')
    expect(screen.getByRole('button', { name: 'Remove Greta Gerwig' })).toBeInTheDocument()
  })

  test('too many requests on the form: the friendly warning', async () => {
    mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/predict': { status: 429, body: { detail: 'x' }, headers: { 'Retry-After': '20' } } })
    renderApp(`/predict?f=${encodeForm(drama.form)}`)
    await userEvent.click(await screen.findByRole('button', { name: /^Predict/ }))
    expect(await screen.findByText("You're going a bit fast. Try again in a minute.")).toBeInTheDocument()
  })
})

describe('links cut or edited by hand', () => {
  const edited = toBase64Url(JSON.stringify({ ...drama.form, runtime: 'long', synopsis: 42 }))

  test('the form loads the rest and names what it reset', async () => {
    mockFetch({ '/api/v1/meta/options': { body: options } })
    renderApp(`/predict?f=${edited}`)
    expect(await screen.findByTestId('link-notice')).toHaveTextContent("Part of this link couldn't be read: runtime, synopsis start from the usual value.")
    expect(await screen.findByRole('button', { name: 'Remove Greta Gerwig' })).toBeInTheDocument()
  })

  test('the results page still predicts the rest, and says so', async () => {
    const { calls } = mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/predict': { body: predictionsJson.small_drama },
      '/api/v1/model-card': { status: 503, body: {} } })
    renderApp(`/predict/result?f=${edited}`)
    expect(await screen.findByTestId('link-notice')).toHaveTextContent('runtime, synopsis were reset to the usual value')
    await screen.findByTestId('card-revenue')
    const body = JSON.parse(String(calls.find(c => c.url.pathname === '/api/v1/predict')!.init?.body))
    expect(body.runtime).toBe(110)
    expect(body.synopsis).toBeUndefined()
  })

  test('browse resets what it can\'t use, an unknown genre too, and says so', async () => {
    expect(browseResets(new URLSearchParams('genre=Drama&page=2&sort=popularity'), options.genres)).toEqual([])
    expect(browseResets(new URLSearchParams('genre=Cartoon&from=abc&score=11&sort=best&page=0'), options.genres))
      .toEqual(['genre', 'from year', 'score', 'sort', 'page'])
    const { calls } = mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/movies': { body: moviesJson as MovieList } })
    renderApp('/browse?genre=Cartoon&page=x')
    expect(await screen.findByTestId('link-notice')).toHaveTextContent("Part of this link couldn't be read, so the genre, page were left at the usual value.")
    await waitFor(() => expect(calls.some(c => c.url.pathname === '/api/v1/movies')).toBe(true))
    expect(calls.filter(c => c.url.pathname === '/api/v1/movies').every(c => !c.url.searchParams.has('genre'))).toBe(true)
  })
})
