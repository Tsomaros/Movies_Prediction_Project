import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { toast } from 'sonner'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { Entry, Me, MovieDetail, MovieList, MyMovieList, Note, NotePage, Options, PersonDetail } from '@/api/client'
import { EXAMPLES } from '@/form/examples'
import { encodeForm } from '@/form/persist'
import { KEY_SAVE_MS, StarRating } from '@/me/StarRating'
import { MY_DEFAULTS, readMyMovies, writeMyMovies } from '@/me/myMovies'
import { VIEW_KEY } from '@/movies/browse'
import { mockFetch } from '@/test/fetch'
import meJson from '@/test/me.json'
import movieJson from '@/test/movie.json'
import moviesJson from '@/test/movies.json'
import myMoviesJson from '@/test/my_movies.json'
import myNotesJson from '@/test/my_notes.json'
import optionsJson from '@/test/options.json'
import personJson from '@/test/person.json'
import predictionsJson from '@/test/predictions.json'
import { renderApp } from '@/test/render'

const ME = meJson as Me
const PERSON = personJson as PersonDetail
const FILM = movieJson as MovieDetail
const LIST = moviesJson as MovieList
const MY_MOVIES = myMoviesJson as MyMovieList
const MY_NOTES = myNotesJson as NotePage

afterEach(() => {
  vi.unstubAllGlobals()
  toast.dismiss() // sonner keeps its toasts between tests (an Undo stays 8 s)
})

const entry = (movie_id: number, body: Partial<Entry> = {}): Entry => ({
  movie_id, status: 'watched', watched_on: '2026-10-01', rating: null,
  added_at: '2026-10-01T10:00:00Z', updated_at: '2026-10-01T10:00:00Z', ...body,
})

const PASSWORD = 'right-pass'

/** The film page's API, logged in or not; `put` answers PUT/DELETE /me/movies/{id} (by default: saves it);
 *  `routes` adds or replaces answers. The password login takes demo / PASSWORD, like the API: 401 for a wrong
 *  one, 422 for an empty (blank) username. */
function serve({ loggedIn = false, entries = [] as Entry[], put, routes = {} }: {
  loggedIn?: boolean; entries?: Entry[]; put?: (init?: RequestInit) => Promise<{ status: number; body?: unknown }>
  routes?: Parameters<typeof mockFetch>[0]
} = {}) {
  let user = loggedIn ? ME.user : null
  const saved = [...entries]
  return mockFetch({
    '/api/v1/meta/options': { body: optionsJson as Options },
    [`/api/v1/movies/${FILM.id}`]: { body: FILM },
    '/api/v1/movies': { body: LIST },
    '/api/v1/auth/me': () => ({ body: { user } }),
    '/api/v1/auth/demo': () => { user = ME.user; return { body: ME } },
    '/api/v1/auth/login': (_url, init) => {
      const { username, password } = JSON.parse(init!.body as string)
      if (!username.trim()) return { status: 422, body: { detail: 'Some fields need fixing', errors: { username: 'string should have at least 1 character' } } }
      if (username !== 'demo' || password !== PASSWORD) return { status: 401, body: { detail: 'Wrong username or password' } }
      user = ME.user
      return { body: ME }
    },
    '/api/v1/auth/logout': () => { user = null; return { status: 204 } },
    '/api/v1/me/movies/status': url => {
      const ids = url.searchParams.get('ids')!.split(',').map(Number)
      return { body: { items: saved.filter(e => ids.includes(e.movie_id)) } }
    },
    [`/api/v1/me/movies/${FILM.id}`]: async (_url, init) => {
      if (put) return put(init)
      const body = init?.body ? JSON.parse(init.body as string) : null
      saved.splice(0, saved.length, ...saved.filter(e => e.movie_id !== FILM.id))
      if (body) saved.push(entry(FILM.id, { status: body.status, rating: body.rating ?? null }))
      return body ? { status: 200, body: saved.at(-1) } : { status: 204 }
    },
    [`/api/v1/me/movies/${FILM.id}/notes`]: { body: { items: [] } },
    '/api/v1/me/movies': { body: MY_MOVIES },
    '/api/v1/me/notes': { body: MY_NOTES },
    ...routes,
  })
}
type Calls = ReturnType<typeof serve>['calls']
const calls = (all: Calls, path: string, method = 'GET') =>
  all.filter(c => c.url.pathname === `/api/v1${path}` && (c.init?.method ?? 'GET') === method)
const lists = () => within(screen.getByRole('radiogroup', { name: 'Your lists' }))

describe('a logged-out click', () => {
  test('opens the login dialog in place, and the action completes after the demo login', async () => {
    const { calls: all } = serve()
    const { router } = renderApp(`/movies/${FILM.id}`)
    await screen.findByRole('heading', { level: 1, name: /Avengers/ })
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', `/login?next=${encodeURIComponent(`/movies/${FILM.id}`)}`)

    await userEvent.click(lists().getByRole('radio', { name: 'Watched' }))
    const dialog = await screen.findByRole('dialog', { name: 'Log in to keep track' })
    expect(calls(all, `/me/movies/${FILM.id}`, 'PUT')).toHaveLength(0)
    await userEvent.click(within(dialog).getByRole('button', { name: /Try the demo account/ }))

    await waitFor(() => expect(calls(all, `/me/movies/${FILM.id}`, 'PUT')).toHaveLength(1))
    expect(JSON.parse(calls(all, `/me/movies/${FILM.id}`, 'PUT')[0].init!.body as string)).toEqual({ status: 'watched' })
    await waitFor(() => expect(lists().getByRole('radio', { name: 'Watched' })).toHaveAttribute('aria-checked', 'true'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Account menu for demo' })).toHaveTextContent('Demo')
    expect(router.state.location.pathname).toBe(`/movies/${FILM.id}`) // the visitor stays on the page
  })

  test('closing the dialog drops the action', async () => {
    const { calls: all } = serve()
    renderApp(`/movies/${FILM.id}`)
    await userEvent.click(await screen.findByRole('radio', { name: 'Plan to watch' }))
    await screen.findByRole('dialog')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls(all, '/auth/demo', 'POST')).toHaveLength(0)
    expect(calls(all, `/me/movies/${FILM.id}`, 'PUT')).toHaveLength(0)
  })
})

describe('optimistic list changes', () => {
  test('a button changes at once and rolls back with a toast when the server fails', async () => {
    let answer!: (reply: { status: number; body?: unknown }) => void
    serve({ loggedIn: true, put: () => new Promise(resolve => { answer = resolve }) })
    renderApp(`/movies/${FILM.id}`)
    const watched = await screen.findByRole('radio', { name: 'Watched' })
    await waitFor(() => expect(lists().getByRole('radio', { name: 'Not in a list' })).toHaveAttribute('aria-checked', 'true'))

    await userEvent.click(watched)
    await waitFor(() => expect(watched).toHaveAttribute('aria-checked', 'true')) // before the server answers
    expect(screen.getByRole('radiogroup', { name: 'Your rating' })).toBeInTheDocument()

    await act(async () => answer({ status: 500, body: { detail: 'boom' } }))
    await waitFor(() => expect(lists().getByRole('radio', { name: 'Not in a list' })).toHaveAttribute('aria-checked', 'true'))
    expect(await screen.findByText('Something went wrong on our side. Please try again.')).toBeInTheDocument()
  })

  test('moving a rated film to the watchlist offers Undo, which puts the rating back', async () => {
    const { calls: all } = serve({ loggedIn: true, entries: [entry(FILM.id, { rating: 8 })] })
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByTestId('film-your-rating')).toHaveTextContent('You: 8/10') // next to the TMDB score
    await userEvent.click(lists().getByRole('radio', { name: 'Plan to watch' }))
    expect(await screen.findByText('Rating removed')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Undo' }))
    await waitFor(() => expect(calls(all, `/me/movies/${FILM.id}`, 'PUT')).toHaveLength(2))
    const undo = JSON.parse(calls(all, `/me/movies/${FILM.id}`, 'PUT')[1].init!.body as string)
    expect(undo).toEqual({ status: 'watched', watched_on: '2026-10-01', rating: 8 })
  })
})

describe('the stars', () => {
  test('work by keyboard, announce "n out of 10" and save once after the keys stop', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const onChange = vi.fn()
      render(<StarRating value={null} onChange={onChange} />)
      expect(screen.getByText('Not rated')).toBeInTheDocument()
      const first = screen.getByRole('radio', { name: '1 out of 10' })
      expect(first).toHaveAttribute('tabindex', '0') // one tab stop for the group
      act(() => first.focus())
      for (let i = 0; i < 3; i++) fireEvent.keyDown(document.activeElement!, { key: 'ArrowRight' })
      expect(screen.getByRole('radio', { name: '3 out of 10' })).toHaveAttribute('aria-checked', 'true')
      expect(document.activeElement).toBe(screen.getByRole('radio', { name: '3 out of 10' }))
      expect(screen.getByText('3/10')).toBeInTheDocument()
      expect(onChange).not.toHaveBeenCalled()
      act(() => { vi.advanceTimersByTime(KEY_SAVE_MS) })
      expect(onChange).toHaveBeenCalledTimes(1)
      expect(onChange).toHaveBeenCalledWith(3)
      fireEvent.keyDown(document.activeElement!, { key: 'End' })
      act(() => { vi.advanceTimersByTime(KEY_SAVE_MS) })
      expect(onChange).toHaveBeenLastCalledWith(10)
    } finally {
      vi.useRealTimers()
    }
  })

  test('a click saves at once, and clicking the current star clears it', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<StarRating value={null} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: '7 out of 10' }))
    expect(onChange).toHaveBeenLastCalledWith(7)
    rerender(<StarRating value={7} onChange={onChange} />)
    expect(screen.getByText('7/10')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: '7 out of 10' }))
    expect(onChange).toHaveBeenLastCalledWith(null)
  })
})

describe('My movies', () => {
  test('tab, sort and page round-trip through the URL; anything odd falls back', () => {
    const state = { tab: 'plan_to_watch' as const, sort: 'title' as const, page: 2 }
    expect(readMyMovies(new URLSearchParams(writeMyMovies(state)))).toEqual(state)
    expect(writeMyMovies(MY_DEFAULTS)).toBe('')
    expect(readMyMovies(new URLSearchParams('tab=evil&sort=rating&page=-1'))).toEqual({ tab: 'watched', sort: 'rating', page: 1 })
    expect(readMyMovies(new URLSearchParams('tab=plan_to_watch&sort=rating'))).toEqual({ tab: 'plan_to_watch', sort: 'added', page: 1 })
  })

  test('the page asks for the URL tab, sort and page, shows the counts and writes a new tab to the URL', async () => {
    const { calls: all } = serve({ loggedIn: true })
    const { router } = renderApp('/my-movies?tab=plan_to_watch&sort=title&page=2')
    await screen.findByRole('heading', { level: 1, name: 'My movies' })
    await waitFor(() => expect(calls(all, '/me/movies')).toHaveLength(1))
    expect(Object.fromEntries(calls(all, '/me/movies')[0].url.searchParams)).toEqual({ status: 'plan_to_watch', sort: 'title', page: '2' })
    const tab = await screen.findByRole('tab', { name: /^Watched/ })
    await waitFor(() => expect(tab).toHaveTextContent(`Watched${MY_MOVIES.counts.watched}`))
    expect(screen.getByText(/Demo data resets every night/)).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Films' })).getAllByTestId('status-badge')).toHaveLength(MY_MOVIES.items.length)

    await userEvent.click(screen.getByRole('tab', { name: /^Notes/ }))
    expect(router.state.location.search).toBe('?tab=notes')
    expect(await screen.findByText(MY_NOTES.items[0].body)).toBeInTheDocument()
    await userEvent.click(tab)
    expect(router.state.location.search).toBe('')
  })

  test('logged out, it offers the demo login', async () => {
    serve()
    renderApp('/my-movies')
    expect(await screen.findByRole('button', { name: /Try the demo account/ })).toBeInTheDocument()
  })
})

describe('the browse grid, logged in', () => {
  test('one status request per page gives each poster a labelled badge and quick buttons', async () => {
    const [first, second] = LIST.items
    const { calls: all } = serve({ loggedIn: true, entries: [entry(first.id, { rating: 9 }), entry(second.id, { status: 'plan_to_watch' })] })
    renderApp('/browse')
    const films = await screen.findByRole('list', { name: 'Films' })
    await waitFor(() => expect(within(films).getAllByTestId('status-badge')).toHaveLength(2))
    expect(calls(all, '/me/movies/status')).toHaveLength(1)
    expect(calls(all, '/me/movies/status')[0].url.searchParams.get('ids'))
      .toBe(LIST.items.map(f => f.id).sort((a, b) => a - b).join(',')) // sorted, so a re-sorted page asks nothing new
    expect(within(films).getByText('Watched, rated 9/10')).toBeInTheDocument()
    expect(within(films).getByText('On your watchlist')).toBeInTheDocument()
    expect(within(films).getByRole('button', { name: `Plan to watch: ${second.title}` })).toHaveAttribute('aria-pressed', 'true')
  })

  test('logged out there are no badges, buttons or status requests', async () => {
    const { calls: all } = serve()
    renderApp('/browse')
    const films = await screen.findByRole('list', { name: 'Films' })
    expect(within(films).queryByRole('button')).not.toBeInTheDocument()
    expect(calls(all, '/me/movies/status')).toHaveLength(0)
  })
})

describe('the account menu', () => {
  test('logs out, after which nothing private stays', async () => {
    const { calls: all } = serve({ loggedIn: true, entries: [entry(FILM.id, { rating: 6 })] })
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByTestId('film-your-rating')).toHaveTextContent('6/10')
    await userEvent.click(screen.getByRole('button', { name: 'Account menu for demo' }))
    expect(await screen.findByRole('menuitem', { name: /My movies/ })).toHaveAttribute('href', '/my-movies')
    await userEvent.click(screen.getByRole('menuitem', { name: /Log out/ }))
    expect(await screen.findByRole('link', { name: 'Log in' })).toBeInTheDocument()
    expect(calls(all, '/auth/logout', 'POST')).toHaveLength(1)
    expect(screen.queryByTestId('film-your-rating')).not.toBeInTheDocument()
    expect(lists().getByRole('radio', { name: 'Not in a list' })).toHaveAttribute('aria-checked', 'true')
  })
})

describe('the password login', () => {
  const openForm = async () => {
    await userEvent.click(await screen.findByRole('button', { name: 'Log in with password' }))
    return screen.getByRole('form', { name: 'Log in with password' })
  }
  const fill = async (form: HTMLElement, username: string, password: string) => {
    if (username) await userEvent.type(within(form).getByLabelText('Username'), username)
    if (password) await userEvent.type(within(form).getByLabelText('Password'), password)
    await userEvent.click(within(form).getByRole('button', { name: 'Log in' }))
  }

  test('logs in and goes back to where the visitor came from', async () => {
    const { calls: all } = serve()
    const { router } = renderApp(`/login?next=${encodeURIComponent(`/movies/${FILM.id}`)}`)
    await fill(await openForm(), 'demo', PASSWORD)
    await waitFor(() => expect(router.state.location.pathname).toBe(`/movies/${FILM.id}`))
    expect(JSON.parse(calls(all, '/auth/login', 'POST')[0].init!.body as string)).toEqual({ username: 'demo', password: PASSWORD })
    expect(await screen.findByRole('button', { name: 'Account menu for demo' })).toBeInTheDocument()
  })

  test('a wrong password says so in the form and stays on the page; the right one then works', async () => {
    serve()
    const { router } = renderApp('/login')
    const form = await openForm()
    await fill(form, 'demo', 'wrong')
    expect(await within(form).findByRole('alert')).toHaveTextContent('Wrong username or password')
    expect(router.state.location.pathname).toBe('/login')
    await userEvent.clear(within(form).getByLabelText('Password'))
    await fill(form, '', PASSWORD)
    await waitFor(() => expect(router.state.location.pathname).toBe('/my-movies')) // no ?next=: My movies
  })

  test('missing fields: empty boxes never reach the server, a blank username gets a clear message', async () => {
    const { calls: all } = serve()
    renderApp('/login')
    const form = await openForm()
    await fill(form, '', '')
    await fill(form, '', 'something') // the username is still empty
    expect(calls(all, '/auth/login', 'POST')).toHaveLength(0)
    await userEvent.type(within(form).getByLabelText('Username'), '   ')
    await userEvent.click(within(form).getByRole('button', { name: 'Log in' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent('Fill in both the username and the password.')
    expect(calls(all, '/auth/login', 'POST')).toHaveLength(1)
  })

  test('a failing demo login shows a toast and stays logged out', async () => {
    serve({ routes: { '/api/v1/auth/demo': { status: 500, body: { detail: 'boom' } } } })
    renderApp('/login')
    await userEvent.click(await screen.findByRole('button', { name: /Try the demo account/ }))
    expect(await screen.findByText('Something went wrong on our side. Please try again.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in' })).toBeInTheDocument()
  })
})

describe('the login page when already logged in', () => {
  test.each([
    [`/movies/${FILM.id}`, `/movies/${FILM.id}`],
    ['//evil.example/path', '/my-movies'], // only a path on this site
    ['https://evil.example', '/my-movies'],
  ])('?next=%s goes to %s', async (next, to) => {
    serve({ loggedIn: true })
    const { router } = renderApp(`/login?next=${encodeURIComponent(next)}`)
    await waitFor(() => expect(router.state.location.pathname).toBe(to))
  })
})

describe('My movies, other states', () => {
  test('an empty tab says what to do and links to Browse', async () => {
    serve({ loggedIn: true, routes: { '/api/v1/me/movies': { body: { ...MY_MOVIES, items: [], total: 0, pages: 0 } } } })
    renderApp('/my-movies?tab=plan_to_watch')
    const empty = await screen.findByTestId('my-empty')
    expect(empty).toHaveTextContent('Nothing on your watchlist yet')
    expect(within(empty).getByRole('link', { name: 'Browse films' })).toHaveAttribute('href', '/browse')
  })

  test('notes that fail to load can be retried', async () => {
    let fail = true
    const { calls: all } = serve({
      loggedIn: true,
      routes: { '/api/v1/me/notes': () => fail ? { status: 500, body: { detail: 'boom' } } : { body: MY_NOTES } },
    })
    renderApp('/my-movies?tab=notes')
    expect(await screen.findByRole('alert')).toHaveTextContent("Your notes couldn't load")
    fail = false
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText(MY_NOTES.items[0].body)).toBeInTheDocument()
    expect(calls(all, '/me/notes')).toHaveLength(2)
  })
})

describe('the quick buttons on a card', () => {
  test('add a film to a list, and a pressed one takes it out', async () => {
    const [first, second] = LIST.items
    const answer = (_url: URL, init?: RequestInit) =>
      init?.method === 'DELETE' ? { status: 204 } : { body: entry(first.id, JSON.parse(init!.body as string)) }
    const { calls: all } = serve({
      loggedIn: true, entries: [entry(second.id, { status: 'plan_to_watch' })],
      routes: { [`/api/v1/me/movies/${first.id}`]: answer, [`/api/v1/me/movies/${second.id}`]: answer },
    })
    renderApp('/browse')
    const films = await screen.findByRole('list', { name: 'Films' })
    const planned = await within(films).findByRole('button', { name: `Plan to watch: ${second.title}` })
    await waitFor(() => expect(planned).toHaveAttribute('aria-pressed', 'true'))

    await userEvent.click(within(films).getByRole('button', { name: `Watched: ${first.title}` }))
    await waitFor(() => expect(calls(all, `/me/movies/${first.id}`, 'PUT')).toHaveLength(1))
    expect(JSON.parse(calls(all, `/me/movies/${first.id}`, 'PUT')[0].init!.body as string)).toEqual({ status: 'watched' })

    await userEvent.click(planned)
    await waitFor(() => expect(calls(all, `/me/movies/${second.id}`, 'DELETE')).toHaveLength(1))
  })
})

describe('quick buttons on every list of films', () => {
  afterEach(() => { try { localStorage.removeItem(VIEW_KEY) } catch { /* storage can fail */ } })
  const [first, second] = LIST.items

  test('home rows: a badge and buttons, and a click saves', async () => {
    const answer = (_url: URL, init?: RequestInit) => ({ body: entry(first.id, JSON.parse(init!.body as string)) })
    const { calls: all } = serve({ loggedIn: true, entries: [entry(second.id, { status: 'plan_to_watch' })],
      routes: { [`/api/v1/me/movies/${first.id}`]: answer } })
    renderApp('/movies')
    await waitFor(() => expect(screen.getAllByText('On your watchlist').length).toBeGreaterThan(0))
    await userEvent.click(screen.getAllByRole('button', { name: `Watched: ${first.title}` })[0])
    await waitFor(() => expect(calls(all, `/me/movies/${first.id}`, 'PUT')).toHaveLength(1))
  })

  test('a person page with 85 films asks for their statuses in two requests', async () => {
    const films = PERSON.roles.find(r => r.role === 'acting')!.films
    const [early, late] = [films[0], films.at(-1)!]
    const { calls: all } = serve({ loggedIn: true, entries: [entry(early.id), entry(late.id, { status: 'plan_to_watch' })],
      routes: { [`/api/v1/people/${PERSON.id}`]: { body: PERSON } } })
    renderApp(`/people/${PERSON.id}`)
    const grid = await screen.findByRole('list', { name: 'Films' })
    await waitFor(() => expect(within(grid).getAllByTestId('status-badge')).toHaveLength(2))
    expect(calls(all, '/me/movies/status')).toHaveLength(2)
    expect(within(grid).getByRole('button', { name: `Plan to watch: ${late.title}` })).toHaveAttribute('aria-pressed', 'true')
    expect(within(grid).getAllByRole('button', { name: /^Watched: / })).toHaveLength(films.length)
  })

  test("a film page's similar films", async () => {
    const similar = FILM.similar[1]
    serve({ loggedIn: true, entries: [entry(similar.id, { rating: 8 })] })
    renderApp(`/movies/${FILM.id}`)
    const section = within((await screen.findByRole('heading', { name: 'Similar films' })).closest('section')!)
    expect(await section.findByText('Watched, rated 8/10')).toBeInTheDocument()
    expect(section.getByRole('button', { name: `Watched: ${similar.title}` })).toHaveAttribute('aria-pressed', 'true')
    expect(section.getAllByRole('button', { name: /^Plan to watch: / })).toHaveLength(FILM.similar.length)
  })

  test('the browse list view', async () => {
    localStorage.setItem(VIEW_KEY, 'list')
    serve({ loggedIn: true, entries: [entry(first.id)] })
    renderApp('/browse')
    const films = await screen.findByRole('list', { name: 'Films' })
    await waitFor(() => expect(within(films).getAllByTestId('status-badge')).toHaveLength(1))
    expect(within(films).getByRole('button', { name: `Watched: ${first.title}` })).toHaveAttribute('aria-pressed', 'true')
  })

  test("the results page's films like yours", async () => {
    const prediction = predictionsJson.small_drama
    const like = prediction.comparables[0]
    serve({ loggedIn: true, entries: [entry(like.id, { status: 'plan_to_watch' })],
      routes: { '/api/v1/predict': { body: prediction } } })
    renderApp(`/predict/result?f=${encodeForm(EXAMPLES.find(e => e.key === 'small_drama')!.form)}`)
    const section = within((await screen.findByRole('heading', { name: 'Films like yours' })).closest('section')!)
    expect(await section.findByText('On your watchlist')).toBeInTheDocument()
    expect(section.getByRole('button', { name: `Plan to watch: ${like.title}` })).toHaveAttribute('aria-pressed', 'true')
  })

  test('logged out: no buttons and no status requests on these pages', async () => {
    const { calls: all } = serve({ routes: { [`/api/v1/people/${PERSON.id}`]: { body: PERSON } } })
    renderApp(`/people/${PERSON.id}`)
    const grid = await screen.findByRole('list', { name: 'Films' })
    expect(within(grid).queryByRole('button')).not.toBeInTheDocument()
    renderApp(`/movies/${FILM.id}`)
    await screen.findByRole('heading', { name: 'Similar films' })
    expect(screen.queryByRole('button', { name: /^Watched: / })).not.toBeInTheDocument()
    expect(calls(all, '/me/movies/status')).toHaveLength(0)
  })
})

describe('notes on a film page', () => {
  /** A small notes store behind the film's notes endpoints (ids from 1, newest first). */
  function serveNotes(loggedIn = true) {
    let notes: Note[] = []
    let next = 1
    const note = (id: number, body: string): Note =>
      ({ id, movie_id: FILM.id, body, created_at: '2026-10-24T09:00:00Z', updated_at: '2026-10-24T09:00:00Z' })
    const byId = (url: URL, init?: RequestInit) => {
      const id = Number(url.pathname.split('/').at(-1))
      if (!notes.some(n => n.id === id)) return { status: 404, body: { detail: 'No such note' } }
      if (init?.method === 'DELETE') { notes = notes.filter(n => n.id !== id); return { status: 204 } }
      const body = JSON.parse(init!.body as string).body
      notes = notes.map(n => n.id === id ? { ...n, body, updated_at: '2026-10-24T09:05:00Z' } : n)
      return { body: notes.find(n => n.id === id) }
    }
    return serve({
      loggedIn,
      routes: {
        [`/api/v1/me/movies/${FILM.id}/notes`]: (_url, init) => {
          if (init?.method !== 'POST') return { body: { items: notes } }
          const added = note(next++, JSON.parse(init.body as string).body)
          notes = [added, ...notes]
          return { status: 201, body: added }
        },
        '/api/v1/me/notes/1': byId, '/api/v1/me/notes/2': byId, '/api/v1/me/notes/3': byId,
      },
    })
  }
  const notesList = () => screen.getByRole('list', { name: 'Notes, newest first' })

  test('add with Ctrl+Enter (trimmed, with a counter), edit in place, Escape cancels', async () => {
    const { calls: all } = serveNotes()
    renderApp(`/movies/${FILM.id}`)
    const box = await screen.findByRole('textbox', { name: 'New note' })
    expect(screen.getByRole('button', { name: 'Add note' })).toBeDisabled() // nothing to save yet
    await userEvent.type(box, '  Thanos wins  ')
    expect(screen.getByText('15 / 2,000')).toBeInTheDocument()
    await userEvent.keyboard('{Control>}{Enter}{/Control}')
    expect(await within(await screen.findByRole('list', { name: 'Notes, newest first' })).findByText('Thanos wins')).toBeInTheDocument()
    expect(box).toHaveValue('')
    expect(JSON.parse(calls(all, `/me/movies/${FILM.id}/notes`, 'POST')[0].init!.body as string)).toEqual({ body: 'Thanos wins' })

    await userEvent.click(within(notesList()).getByRole('button', { name: 'Edit note' }))
    const edit = screen.getByRole('textbox', { name: 'Edit note' })
    await userEvent.type(edit, ' (for now){Escape}')
    expect(within(notesList()).getByText('Thanos wins')).toBeInTheDocument() // cancelled
    expect(calls(all, '/me/notes/1', 'PATCH')).toHaveLength(0)

    await userEvent.click(within(notesList()).getByRole('button', { name: 'Edit note' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Edit note' }), ' (for now)')
    await userEvent.click(within(notesList()).getByRole('button', { name: 'Save' }))
    expect(await within(notesList()).findByText('Thanos wins (for now)')).toBeInTheDocument()
    expect(within(notesList()).getByText(/edited/)).toBeInTheDocument()
  })

  test('delete takes the note away at once and Undo adds it back', async () => {
    const { calls: all } = serveNotes()
    renderApp(`/movies/${FILM.id}`)
    await userEvent.type(await screen.findByRole('textbox', { name: 'New note' }), 'Keep this one')
    await userEvent.click(screen.getByRole('button', { name: 'Add note' }))
    await userEvent.click(await within(await screen.findByRole('list', { name: 'Notes, newest first' })).findByRole('button', { name: 'Delete note' }))
    await waitFor(() => expect(screen.queryByText('Keep this one')).not.toBeInTheDocument())
    expect(calls(all, '/me/notes/1', 'DELETE')).toHaveLength(1)
    await userEvent.click(await screen.findByRole('button', { name: 'Undo' }))
    expect(await within(await screen.findByRole('list', { name: 'Notes, newest first' })).findByText('Keep this one')).toBeInTheDocument()
    expect(calls(all, `/me/movies/${FILM.id}/notes`, 'POST')).toHaveLength(2)
  })

  test('a delete the server refuses puts the note back with a toast', async () => {
    serveNotes()
    renderApp(`/movies/${FILM.id}`)
    await userEvent.type(await screen.findByRole('textbox', { name: 'New note' }), 'Stubborn')
    await userEvent.click(screen.getByRole('button', { name: 'Add note' }))
    const list = await screen.findByRole('list', { name: 'Notes, newest first' })
    vi.mocked(fetch).mockImplementationOnce(async () => new Response('{"detail":"boom"}', { status: 500 }))
    await userEvent.click(await within(list).findByRole('button', { name: 'Delete note' }))
    expect(await screen.findByText('Something went wrong on our side. Please try again.')).toBeInTheDocument()
    expect(await within(notesList()).findByText('Stubborn')).toBeInTheDocument()
  })

  test('logged out, the notes offer the login dialog', async () => {
    serveNotes(false)
    renderApp(`/movies/${FILM.id}`)
    expect(screen.queryByRole('textbox', { name: 'New note' })).not.toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: 'Log in to write notes' }))
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: /Try the demo account/ }))
    expect(await screen.findByRole('textbox', { name: 'New note' })).toBeInTheDocument()
  })
})

describe('the watched date', () => {
  test('changing it sends only the date; the rating stays to the server', async () => {
    const { calls: all } = serve({ loggedIn: true, entries: [entry(FILM.id, { rating: 7 })] })
    renderApp(`/movies/${FILM.id}`)
    const date = await screen.findByLabelText('Watched on')
    expect(date).toHaveValue('2026-10-01')
    fireEvent.change(date, { target: { value: '2026-09-15' } })
    await waitFor(() => expect(calls(all, `/me/movies/${FILM.id}`, 'PUT')).toHaveLength(1))
    expect(JSON.parse(calls(all, `/me/movies/${FILM.id}`, 'PUT')[0].init!.body as string)).toEqual({ status: 'watched', watched_on: '2026-09-15' })
    fireEvent.change(date, { target: { value: '' } }) // a cleared box sends nothing
    expect(calls(all, `/me/movies/${FILM.id}`, 'PUT')).toHaveLength(1)
  })
})

describe('accounts down', () => {
  test('a failed /auth/me shows "Log in" and is not asked again on every page or dialog', async () => {
    const { calls: all } = serve({ routes: { '/api/v1/auth/me': { status: 503, body: { detail: "The accounts database isn't answering." } } } })
    const { router } = renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByRole('link', { name: 'Log in' })).toBeInTheDocument()
    await act(() => router.navigate('/browse'))
    await screen.findByRole('heading', { level: 1, name: 'Browse films' })
    expect(screen.getByRole('link', { name: 'Log in' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Surprise me' }))
    await screen.findByRole('dialog', { name: 'Surprise me' })
    window.dispatchEvent(new Event('focus'))
    expect(screen.getByRole('link', { name: 'Log in', hidden: true })).toBeInTheDocument()
    expect(calls(all, '/auth/me')).toHaveLength(1)
  })
})
