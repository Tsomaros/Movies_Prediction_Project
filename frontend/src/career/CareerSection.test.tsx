import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { cloneElement, isValidElement, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import type { CareerModelResponse, CareerResponse, PersonDetail } from '@/api/client'
import { decodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import fewJson from '@/test/career_few.json'
import fewModelJson from '@/test/career_few_model.json'
import nolanJson from '@/test/career_nolan.json'
import fantasyJson from '@/test/career_nolan_fantasy.json'
import nolanModelJson from '@/test/career_nolan_model.json'
import romanceJson from '@/test/career_nolan_romance.json'
import writingJson from '@/test/career_nolan_writing.json'
import oneJson from '@/test/career_one.json'
import { mockFetch } from '@/test/fetch'
import optionsJson from '@/test/options.json'
import personJson from '@/test/person.json'
import personFewJson from '@/test/person_few.json'
import nolanPersonJson from '@/test/person_nolan.json'
import plainJson from '@/test/person_plain.json'
import { renderApp } from '@/test/render'

vi.mock('recharts', async importOriginal => {
  const recharts = await importOriginal<typeof import('recharts')>()
  return {
    ...recharts,
    ResponsiveContainer: ({ children }: { children: ReactNode }) =>
      isValidElement(children) ? cloneElement(children as React.ReactElement<{ width: number; height: number }>, { width: 800, height: 260 }) : null,
  }
})

// Real answers saved from the API: Christopher Nolan directing (with genre chips) and writing, Hanna Hall
// (3 rated films), Abigail Stone (one film), and their person pages.
const NOLAN = nolanPersonJson as PersonDetail
const DIRECTING = nolanJson as CareerResponse
const WRITING = writingJson as CareerResponse
const MODEL = nolanModelJson as CareerModelResponse
const ROMANCE = romanceJson as CareerModelResponse
const FANTASY = fantasyJson as CareerModelResponse

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 25, 12))
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

type Reply = { status?: number; body?: unknown } | Promise<{ status?: number; body?: unknown }>
const later = <T,>() => {
  let resolve!: (v: T) => void
  return { promise: new Promise<T>(r => { resolve = r }), resolve }
}
const wait = (ms: number) => new Promise(r => setTimeout(r, ms))

/** The API for one person page; /career/model answers by genre (`chips`), the default answer otherwise. */
function serve(person: PersonDetail, { career, model, chips = {} }: {
  career: (role: string | null) => Reply; model?: () => Reply; chips?: Record<string, () => Reply>
}) {
  return mockFetch({
    '/api/v1/auth/me': { body: { user: null } },
    '/api/v1/meta/options': { body: optionsJson },
    [`/api/v1/people/${person.id}`]: { body: person },
    [`/api/v1/people/${person.id}/career`]: url => career(url.searchParams.get('role')),
    [`/api/v1/people/${person.id}/career/model`]: url => {
      const genre = url.searchParams.get('genre')
      return genre ? chips[genre]() : (model ?? (() => ({ body: MODEL })))()
    },
  })
}
const nolan = (opts: Partial<Parameters<typeof serve>[1]> = {}) =>
  serve(NOLAN, { career: role => ({ body: role === 'writing' ? WRITING : DIRECTING }), ...opts })
// the first test also waits for the lazy page, section and Recharts to load
const career = () => screen.findByRole('region', { name: 'Career' }, { timeout: 5000 })
const modelCalls = (calls: ReturnType<typeof serve>['calls']) =>
  calls.filter(c => c.url.pathname.endsWith('/career/model')).map(c => c.url.searchParams.get('genre'))

describe('the Career section', () => {
  test('shows the chart, the track-record range and, on request, how it is calculated', async () => {
    nolan()
    renderApp('/people/525')
    const section = await career()
    expect(await within(section).findByText('6.6 – 8.3')).toBeInTheDocument()
    expect(within(section).getByText('Most likely around 7.5')).toBeInTheDocument()
    expect(within(section).getAllByTestId('dot-crew').length).toBeGreaterThan(0)
    expect(within(section).getByTestId('forecast-band')).toBeInTheDocument()
    expect(within(section).queryByText(/out of 10 real next films/)).toBeNull()
    await userEvent.click(within(section).getByRole('button', { name: 'How is this calculated?' }))
    expect(within(section).getByText(/^Based on 12 rated films\. Recent films count more: a film from 3 years before the latest counts half\./))
      .toHaveTextContent('we trust it 77% and the database average (6.4) 23%, giving 7.5. The range is wider for people whose scores vary more. In our tests on films from 2019 onward, 8 out of 10 real next films landed inside a range built this way.')
    expect(within(section).getByText("We only see the most-voted films of each year, so smaller films aren't counted.")).toBeInTheDocument()
    await userEvent.click(within(section).getByRole('button', { name: 'View as table' }))
    expect(within(within(section).getByRole('table', { name: 'Career films' })).getAllByRole('row')).toHaveLength(DIRECTING.films.length + 1)
  })

  test('the page\'s role switch moves the section to writing', async () => {
    const { calls } = nolan()
    const { router } = renderApp('/people/525')
    const section = await career()
    expect(await within(section).findByText('Their usual film')).toBeInTheDocument()
    await userEvent.click(within(screen.getByRole('radiogroup', { name: 'Show their work as' })).getByRole('radio', { name: /Writing/ }))
    expect(router.state.location.search).toBe('?role=writing')
    const writing = await career()
    expect(await within(writing).findByText('Most likely around 7.5')).toBeInTheDocument()
    expect(within(writing).getByText('The film model has no writer input, so only the track record is shown.')).toBeInTheDocument()
    expect(within(writing).queryByText('Their usual film')).toBeNull()
    expect(calls.filter(c => c.url.pathname.endsWith('/career')).map(c => c.url.searchParams.get('role'))).toEqual(['directing', 'writing'])
    expect(modelCalls(calls)).toEqual([null]) // directing only
  })

  test('the model card: a skeleton, then both films with the honesty line', async () => {
    const reply = later<{ body: unknown }>()
    const { calls } = nolan({ model: () => reply.promise })
    renderApp('/people/525')
    const section = await career()
    expect(await within(section).findByTestId('model-skeleton')).toBeInTheDocument()
    reply.resolve({ body: MODEL })
    expect(await within(section).findByText('Their usual film')).toBeInTheDocument()
    expect(within(section).queryByTestId('model-skeleton')).toBeNull()
    expect(within(section).getByText('Something new')).toBeInTheDocument()
    expect(within(section).getByTestId('usual-recipe')).toHaveTextContent(
      'Action, Drama · murder and revenge, based on a book, history and war · Michael Caine, Cillian Murphy, Christian Bale · 2027')
    expect(within(section).getByTestId('new-recipe')).toHaveTextContent('Comedy, Romance · love and marriage, christmas and holidays, based on a book · new collaborators · 2027')
    expect(within(section).getByText("The model doesn't know how they'd handle a new genre; it shows how films like this usually do with someone of their track record.")).toBeInTheDocument()
    expect(within(section).getByRole('button', { name: 'Comedy' })).toHaveAttribute('aria-pressed', 'true')
    // asked only once /career had answered
    expect(calls.findIndex(c => c.url.pathname.endsWith('/career/model'))).toBeGreaterThan(calls.findIndex(c => c.url.pathname.endsWith('/career')))
  })

  test('a slow earlier chip never overwrites a newer choice; the default chip needs no request', async () => {
    const slow = later<{ body: unknown }>()
    const { calls } = nolan({ chips: { 14: () => slow.promise, 10749: () => ({ body: ROMANCE }) } })
    renderApp('/people/525')
    const section = await career()
    await userEvent.click(await within(section).findByRole('button', { name: 'Fantasy' }))
    expect(within(section).getByTestId('new-recipe').closest('[aria-busy]')).toHaveAttribute('aria-busy', 'true') // old numbers, faded
    expect(within(section).getByTestId('new-recipe')).toHaveTextContent(/^Comedy, Romance/)
    await userEvent.click(within(section).getByRole('button', { name: 'Romance' }))
    await waitFor(() => expect(within(section).getByTestId('new-recipe')).toHaveTextContent(/^Romance, Comedy/))
    expect(within(section).getByRole('button', { name: 'Romance' })).toHaveAttribute('aria-pressed', 'true')
    slow.resolve({ body: FANTASY })
    await wait(50)
    expect(within(section).getByTestId('new-recipe')).toHaveTextContent(/^Romance, Comedy/)
    expect(within(section).getByTestId('new-recipe')).not.toHaveTextContent('Fantasy')
    expect(within(section).getByTestId('new-recipe').closest('[aria-busy]')).toHaveAttribute('aria-busy', 'false')
    await userEvent.click(within(section).getByRole('button', { name: 'Comedy' }))
    expect(within(section).getByTestId('new-recipe')).toHaveTextContent(/^Comedy, Romance/)
    expect(modelCalls(calls)).toEqual([null, '14', '10749'])
  })

  test('a failed model forecast offers Retry, and the chart and track record stay', async () => {
    let fail = true
    nolan({ model: () => (fail ? { status: 500, body: {} } : { body: MODEL }) })
    renderApp('/people/525')
    const section = await career()
    expect(await within(section).findByText("Couldn't load the model forecast.", {}, { timeout: 3000 })).toBeInTheDocument() // after one retry
    expect(within(section).getByText('6.6 – 8.3')).toBeInTheDocument()
    expect(within(section).getByTestId('forecast-band')).toBeInTheDocument()
    fail = false
    await userEvent.click(within(section).getByRole('button', { name: 'Retry' }))
    expect(await within(section).findByText('Their usual film')).toBeInTheDocument()
  })

  test('a failed career chart offers Retry, and the rest of the page still renders', async () => {
    let fail = true
    nolan({ career: () => (fail ? { status: 500, body: {} } : { body: DIRECTING }) })
    renderApp('/people/525')
    const section = await career()
    expect(await within(section).findByText("Couldn't load the career chart.", {}, { timeout: 3000 })).toBeInTheDocument() // after one retry
    expect(screen.getByRole('heading', { level: 1, name: 'Christopher Nolan' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Films' })).toBeInTheDocument()
    fail = false
    await userEvent.click(within(section).getByRole('button', { name: 'Retry' }))
    expect(await within(section).findByText('6.6 – 8.3')).toBeInTheDocument()
  })

  test('fewer than 2 dated films: no chart, just a note', async () => {
    serve(plainJson as PersonDetail, { career: () => ({ body: oneJson }), model: () => ({ body: fewModelJson }) })
    renderApp('/people/55')
    const section = await career()
    expect(await within(section).findByText('Not enough dated films to chart a career')).toBeInTheDocument()
    expect(within(section).queryByTestId(/^dot-/)).toBeNull()
    expect(within(section).queryByRole('radio', { name: 'Score' })).toBeNull()
    expect(within(section).getByText('Not enough rated films to forecast yet (needs 5)')).toBeInTheDocument()
  })

  test('2 to 4 rated films: the chart without a band, and no track-record forecast yet', async () => {
    const few = fewJson as CareerResponse
    serve(personFewJson as PersonDetail, { career: () => ({ body: few }), model: () => ({ body: fewModelJson }) })
    renderApp('/people/204997')
    const section = await career()
    expect(await within(section).findByText('Not enough rated films to forecast yet (needs 5)')).toBeInTheDocument()
    expect(within(section).getAllByTestId(/^dot-/)).toHaveLength(few.films.filter(f => f.score !== null).length)
    expect(within(section).queryByTestId('forecast-band')).toBeNull()
    expect(await within(section).findByText('Their usual film')).toBeInTheDocument()
  })

  test('"Edit in predictor" opens the form with the recipe\'s genres and named people', async () => {
    nolan()
    const { router } = renderApp('/people/525')
    const section = await career()
    await within(section).findByText('Their usual film')
    const [usual] = within(section).getAllByRole('button', { name: 'Edit in predictor' })
    await waitFor(() => expect(usual).toBeEnabled()) // once /meta/options has answered
    await userEvent.click(usual)
    await waitFor(() => expect(router.state.location.pathname).toBe('/predict'))
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get(LIKE_PARAM)).toBe("Christopher Nolan's usual film")
    const form = decodeForm(params.get(URL_PARAM))!
    expect(form.genres).toEqual(['Action', 'Drama'])
    expect(form.director).toEqual({ id: 525, name: 'Christopher Nolan' })
    expect(form.actors.map(a => a.name)).toEqual(['Michael Caine', 'Cillian Murphy', 'Christian Bale'])
    expect([form.release_year, form.budget]).toEqual([2027, MODEL.usual!.recipe.budget_2025])
  })

  test('other roles say what the chart covers, without loading it', async () => {
    const { calls } = serve(personJson as PersonDetail, { career: () => ({ status: 500 }) })
    renderApp('/people/31?role=production')
    expect(await screen.findByText('The career chart covers acting, directing and writing.')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Career' })).toBeNull()
    expect(calls.some(c => c.url.pathname.includes('/career'))).toBe(false)
  })
})
