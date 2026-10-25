import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { toast } from 'sonner'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { Me, Options, RandomPick } from '@/api/client'
import { PREFS_KEY } from '@/surprise/prefs'
import { mockFetch } from '@/test/fetch'
import meJson from '@/test/me.json'
import optionsJson from '@/test/options.json'
import randomJson from '@/test/random.json'
import { renderApp } from '@/test/render'

const ME = meJson as Me
const PICK = randomJson as RandomPick // a real answer: Blade Runner, from the 1980s science fiction films
const OTHER = { ...PICK, movie: { ...PICK.movie!, id: 1, title: 'Another Film' } }
const EMPTY = (reason: RandomPick['reason']): RandomPick => ({ movie: null, reason, shuffle: [], pool: 0 })

afterEach(() => {
  vi.unstubAllGlobals()
  toast.dismiss()
})

/** The API for a page with the header; `answers` are given to GET /random in turn (the last one repeats). */
function serve(answers: RandomPick[], { loggedIn = false } = {}) {
  let user = loggedIn ? ME.user : null
  let n = 0
  return mockFetch({
    '/api/v1/meta/options': { body: optionsJson as Options },
    '/api/v1/auth/me': () => ({ body: { user } }),
    '/api/v1/auth/demo': () => { user = ME.user; return { body: ME } },
    '/api/v1/me/movies/status': { body: { items: [] } },
    '/api/v1/random': () => ({ body: answers[Math.min(n++, answers.length - 1)] }),
  })
}

const randomCalls = (calls: ReturnType<typeof serve>['calls']) =>
  calls.filter(c => c.url.pathname === '/api/v1/random').map(c => Object.fromEntries(c.url.searchParams))

function reduceMotion({ wide = false } = {}) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('reduce') || (wide && query.includes('min-width')), media: query, onchange: null, addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  }))
}

async function choose(trigger: HTMLElement, option: string) {
  await userEvent.click(trigger)
  await userEvent.click(await screen.findByRole('option', { name: option }))
}

async function open() {
  renderApp('/no/such/page') // any page with the header
  await userEvent.click(await screen.findByRole('button', { name: 'Surprise me' }))
  return screen.findByRole('dialog', { name: 'Surprise me' })
}

describe('Surprise me', () => {
  test('a spin shuffles posters for about a second, then shows the film', async () => {
    const { calls } = serve([PICK])
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    expect(await within(dialog).findByTestId('reveal')).toBeInTheDocument()
    expect(within(dialog).queryByRole('heading', { name: 'Blade Runner' })).not.toBeInTheDocument()
    expect(await within(dialog).findByRole('heading', { name: 'Blade Runner' }, { timeout: 3000 })).toBeInTheDocument()
    expect(within(dialog).queryByTestId('reveal')).not.toBeInTheDocument()
    expect(within(dialog).getByText('1982 · 1 h 58 min')).toBeInTheDocument()
    expect(within(dialog).getByTestId('pool')).toHaveTextContent('Picked from 111 films')
    expect(within(dialog).getByRole('link', { name: 'Open details' })).toHaveAttribute('href', '/movies/78')
    expect(randomCalls(calls)).toEqual([{ source: 'all' }])
  })

  test('reopening starts fresh at Spin, not a replay of the last pick, and still never repeats it', async () => {
    const { calls } = serve([PICK, OTHER])
    let dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await within(dialog).findByRole('heading', { name: 'Blade Runner' }, { timeout: 3000 })
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'Surprise me' }))
    dialog = await screen.findByRole('dialog', { name: 'Surprise me' })
    expect(within(dialog).queryByTestId('reveal')).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('heading', { name: 'Blade Runner' })).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await within(dialog).findByRole('heading', { name: 'Another Film' }, { timeout: 3000 })
    expect(randomCalls(calls).map(q => q.exclude)).toEqual([undefined, '78'])
  })

  test('with reduce motion on, the film shows at once', async () => {
    reduceMotion()
    serve([PICK])
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    expect(await within(dialog).findByRole('heading', { name: 'Blade Runner' })).toBeInTheDocument()
    expect(within(dialog).queryByTestId('reveal')).not.toBeInTheDocument()
  })

  test('Spin again sends every earlier pick, so a film never comes back', async () => {
    reduceMotion()
    const { calls } = serve([PICK, OTHER, PICK])
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await within(dialog).findByRole('heading', { name: 'Blade Runner' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin again' }))
    await within(dialog).findByRole('heading', { name: 'Another Film' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin again' }))
    await waitFor(() => expect(randomCalls(calls)).toHaveLength(3))
    expect(randomCalls(calls).map(q => q.exclude)).toEqual([undefined, '78', '78,1'])
  })

  test('the watchlist needs a login: the dialog opens, then the spin completes', async () => {
    reduceMotion()
    const { calls } = serve([PICK])
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('radio', { name: 'From my watchlist' }))
    expect(within(dialog).getByText(/Your watchlist needs a login/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    const login = await screen.findByRole('dialog', { name: 'Log in to keep track' })
    expect(randomCalls(calls)).toEqual([])
    await userEvent.click(within(login).getByRole('button', { name: /Try the demo account/ }))
    expect(await screen.findByRole('heading', { name: 'Blade Runner' })).toBeInTheDocument()
    expect(randomCalls(calls)).toEqual([{ source: 'watchlist' }])
    expect(screen.getByRole('button', { name: 'Mark as watched' })).toBeInTheDocument()
  })

  test('an empty watchlist links to Browse', async () => {
    serve([EMPTY('watchlist_empty')], { loggedIn: true })
    localStorage.setItem(PREFS_KEY, JSON.stringify({ source: 'watchlist' }))
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    const empty = await within(dialog).findByTestId('surprise-empty')
    expect(within(empty).getByRole('heading', { name: 'Add films first' })).toBeInTheDocument()
    expect(within(empty).getByRole('link', { name: 'Browse films' })).toHaveAttribute('href', '/browse')
  })

  test('no match offers to clear the filters, which the browser remembered', async () => {
    const { calls } = serve([EMPTY('no_match')])
    localStorage.setItem(PREFS_KEY, JSON.stringify({ decade: 1960, maxRuntime: 90, gems: true, genre: 'Western' }))
    const dialog = await open()
    expect(within(dialog).getByRole('button', { name: 'Filters (3)' })).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await waitFor(() => expect(randomCalls(calls)).toEqual([
      { source: 'all', genre: 'Western', decade: '1960', max_runtime: '90', gems: 'true' }]))
    const empty = await within(dialog).findByTestId('surprise-empty')
    expect(within(empty).getByRole('heading', { name: 'Loosen a filter' })).toBeInTheDocument()
    await userEvent.click(within(empty).getByRole('button', { name: 'Clear filters' }))
    expect(within(dialog).getByRole('button', { name: 'Filters' })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem(PREFS_KEY)!)).toMatchObject({ genre: null, decade: null, maxRuntime: null, gems: false })
  })

  test('all seen offers to start over, which forgets the earlier picks', async () => {
    reduceMotion()
    const { calls } = serve([PICK, EMPTY('all_seen'), PICK])
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await within(dialog).findByRole('heading', { name: 'Blade Runner' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin again' }))
    const empty = await within(dialog).findByTestId('surprise-empty')
    expect(within(empty).getByRole('heading', { name: "You've seen them all" })).toBeInTheDocument()
    await userEvent.click(within(empty).getByRole('button', { name: 'Start over' }))
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await within(dialog).findByRole('heading', { name: 'Blade Runner' })
    expect(randomCalls(calls).map(q => q.exclude)).toEqual([undefined, '78', undefined])
  })

  test('a broken or odd saved choice falls back to the defaults', async () => {
    const { calls } = serve([PICK])
    localStorage.setItem(PREFS_KEY, JSON.stringify({ source: 'friends', decade: 1965, maxRuntime: 'long', language: 'English' }))
    const dialog = await open()
    expect(within(dialog).getByRole('radio', { name: "Anything I haven't seen" })).toHaveAttribute('aria-checked', 'true')
    expect(within(dialog).getByRole('button', { name: 'Filters' })).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await waitFor(() => expect(randomCalls(calls)).toEqual([{ source: 'all' }]))
  })

  test('a whole-database pick can go on the watchlist', async () => {
    reduceMotion()
    const { calls } = serve([PICK], { loggedIn: true })
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Add to watchlist' }))
    await waitFor(() => expect(calls.some(c => c.url.pathname === '/api/v1/me/movies/78' && c.init?.method === 'PUT')).toBe(true))
    const put = calls.find(c => c.url.pathname === '/api/v1/me/movies/78')!
    expect(JSON.parse(put.init!.body as string)).toEqual({ status: 'plan_to_watch' })
  })

  test('on a wide screen it is a dialog; the filters chosen go to the API and are remembered', async () => {
    reduceMotion({ wide: true })
    const { calls } = serve([PICK])
    const dialog = await open()
    expect(dialog).not.toHaveAttribute('data-side') // the sheet carries data-side="bottom"
    await userEvent.click(within(dialog).getByRole('button', { name: 'Filters' }))
    await choose(within(dialog).getByRole('combobox', { name: 'Genre' }), 'Science Fiction')
    await choose(within(dialog).getByRole('combobox', { name: 'Decade' }), '1980s')
    await choose(within(dialog).getByRole('combobox', { name: 'Language' }), 'English')
    await choose(within(dialog).getByRole('combobox', { name: 'Runtime' }), 'Up to 120 min')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /Include hidden gems/ }))
    expect(within(dialog).getByRole('button', { name: 'Filters (4)' })).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await within(dialog).findByRole('heading', { name: 'Blade Runner' })
    expect(randomCalls(calls)).toEqual([
      { source: 'all', genre: 'Science Fiction', decade: '1980', language: 'en', max_runtime: '120', gems: 'true' }])
    expect(JSON.parse(localStorage.getItem(PREFS_KEY)!)).toEqual(
      { source: 'all', genre: 'Science Fiction', decade: 1980, language: 'en', maxRuntime: 120, gems: true })
    await choose(within(dialog).getByRole('combobox', { name: 'Decade' }), 'Any decade')
    expect(within(dialog).getByRole('button', { name: 'Filters (3)' })).toBeInTheDocument()
  })

  test('a watchlist pick can be marked as watched', async () => {
    reduceMotion()
    const { calls } = serve([PICK], { loggedIn: true })
    localStorage.setItem(PREFS_KEY, JSON.stringify({ source: 'watchlist', gems: true }))
    const dialog = await open()
    expect(within(dialog).queryByRole('checkbox', { name: /Include hidden gems/ })).not.toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Mark as watched' }))
    await waitFor(() => expect(calls.some(c => c.url.pathname === '/api/v1/me/movies/78')).toBe(true))
    const put = calls.find(c => c.url.pathname === '/api/v1/me/movies/78')!
    expect(JSON.parse(put.init!.body as string)).toEqual({ status: 'watched' })
    expect(randomCalls(calls)).toEqual([{ source: 'watchlist' }]) // gems only count for the whole database
  })

  test('too many spins say so in a toast and keep the dialog as it was', async () => {
    mockFetch({
      '/api/v1/auth/me': { body: { user: null } },
      '/api/v1/random': { status: 429, body: { detail: 'Too many spins in a minute.' }, headers: { 'Retry-After': '30' } },
    })
    const dialog = await open()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Spin' }))
    expect(await screen.findByText("You're going a bit fast. Try again in a minute.")).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Spin' })).toBeEnabled()
  })
})
