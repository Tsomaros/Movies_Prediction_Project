// The header search (V1.1) inside the real app: modes, quick results, the keyboard, the hint, errors, the phone
// overlay, the "/" shortcut and the Series page. Answers are real API answers (movies.json, people_search_hanks.json).
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { mockFetch } from '@/test/fetch'
import { renderApp } from '@/test/render'
import { mockSystemTheme } from '@/test/setup'
import movies from '@/test/movies.json'
import hanks from '@/test/people_search_hanks.json'

const NO_MOVIES = { items: [], total: 0, page: 1, page_size: 5, pages: 0 }

afterEach(() => mockSystemTheme(false))

function api({ moviesBody = movies as unknown, people = hanks as unknown, moviesError = false } = {}) {
  return mockFetch({
    '/api/v1/movies': () => moviesError ? { status: 500, body: { detail: 'boom' } } : { body: moviesBody },
    '/api/v1/people/search': url => ({ body: { ...(people as object), q: url.searchParams.get('q') } }),
  })
}

const box = () => screen.getByRole('combobox', { name: /search/i })
/** The real app at `path`, once its (lazy) page has loaded and the header is there. */
async function start(path: string) {
  const out = renderApp(path)
  await screen.findByRole('combobox', { name: /search/i })
  return out
}
const calls = (fetch: ReturnType<typeof api>, path: string) => fetch.calls.filter(c => c.url.pathname === path)

test('the placeholder follows the mode, which is remembered off the results pages', async () => {
  const first = await start('/about')
  expect(box()).toHaveAttribute('placeholder', 'Search movies…')
  await userEvent.click(screen.getByRole('radio', { name: 'People' }))
  expect(box()).toHaveAttribute('placeholder', 'Search actors, directors, writers…')
  expect(box()).toHaveFocus()
  first.unmount()
  await start('/login')
  expect(screen.getByRole('radio', { name: 'People' })).toHaveAttribute('aria-checked', 'true')
})

test('nothing is asked under 2 letters; then one request after the pause', async () => {
  const fetch = api()
  await start('/about')
  await userEvent.type(box(), 't')
  await new Promise(r => setTimeout(r, 400))
  expect(calls(fetch, '/api/v1/movies')).toHaveLength(0)
  await userEvent.type(box(), 'om')
  await screen.findAllByRole('option')
  expect(calls(fetch, '/api/v1/movies').map(c => c.url.search)).toEqual(['?q=tom&page_size=5'])
})

test('five rows and the see-all row; Enter without the arrows opens the results page', async () => {
  api()
  const { router } = await start('/predict/compare')
  await userEvent.type(box(), 'tom')
  expect(await screen.findAllByRole('option')).toHaveLength(6)
  expect(screen.getByText('See all 79,199 results for ‘tom’')).toBeInTheDocument()
  expect(screen.getByText('Clue')).toBeInTheDocument()
  expect(box()).not.toHaveAttribute('aria-activedescendant')
  await userEvent.keyboard('{Enter}')
  await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe('/browse?q=tom'))
})

test('ArrowDown then Enter opens the highlighted film, and the box is cleared', async () => {
  api()
  const { router } = await start('/about')
  await userEvent.type(box(), 'tom')
  await screen.findAllByRole('option')
  await userEvent.keyboard('{ArrowDown}')
  expect(box().getAttribute('aria-activedescendant')).toMatch(/-0$/)
  await userEvent.keyboard('{Enter}')
  await waitFor(() => expect(router.state.location.pathname).toBe('/movies/15196'))
  await waitFor(() => expect(box()).toHaveValue(''))
})

test('people rows show their roles and known-for film and link to the person', async () => {
  api()
  const { router } = await start('/about')
  await userEvent.click(screen.getByRole('radio', { name: 'People' }))
  await userEvent.type(box(), 'hanks')
  expect(await screen.findByText(/^Actor, Writer, Director/)).toBeInTheDocument()
  expect(screen.getByText(/^Actor · 8 films/)).toBeInTheDocument()
  await userEvent.click(screen.getByText('Tom Hanks'))
  await waitFor(() => expect(router.state.location.pathname).toBe('/people/31'))
})

test('an empty search points to the other mode, which is asked only then', async () => {
  const fetch = api({ moviesBody: NO_MOVIES })
  await start('/about')
  await userEvent.type(box(), 'tom hanks')
  expect(await screen.findByText('No movies match ‘tom hanks’.')).toBeInTheDocument()
  const hint = await screen.findByRole('link', { name: /13 people found/ })
  expect(hint).toHaveAttribute('href', '/people?q=tom%20hanks')
  expect(calls(fetch, '/api/v1/people/search')).toHaveLength(1)
  expect(screen.getByText('No movies found, 13 people found')).toBeInTheDocument() // the live region
})

test('with results, the other mode is never asked', async () => {
  const fetch = api()
  await start('/about')
  await userEvent.type(box(), 'tom')
  await screen.findAllByRole('option')
  expect(calls(fetch, '/api/v1/people/search')).toHaveLength(0)
})

test('on a results page the box holds its text, and switching the mode opens the other results page', async () => {
  api()
  const { router } = await start('/browse?q=nolan&genre=Drama')
  expect(box()).toHaveValue('nolan')
  expect(screen.getByRole('radio', { name: 'Movies' })).toHaveAttribute('aria-checked', 'true')
  await userEvent.click(screen.getByRole('radio', { name: 'People' }))
  await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe('/people?q=nolan'))
  router.navigate(-1)
  await waitFor(() => expect(router.state.location.pathname).toBe('/browse'))
})

test('on a results page with no text, People still opens the people page', async () => {
  api()
  const { router } = await start('/browse')
  await userEvent.click(screen.getByRole('radio', { name: 'People' }))
  await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe('/people'))
  expect(screen.getByRole('radio', { name: 'People' })).toHaveAttribute('aria-checked', 'true')
})

test('the arrow keys switch the mode from the switch itself', async () => {
  api()
  await start('/about')
  screen.getByRole('radio', { name: 'Movies' }).focus()
  await userEvent.keyboard('{ArrowRight}')
  expect(screen.getByRole('radio', { name: 'People' })).toHaveAttribute('aria-checked', 'true')
})

test('an error offers Retry; Esc closes the list, a second Esc leaves the box', async () => {
  const fetch = api({ moviesError: true })
  await start('/about')
  await userEvent.type(box(), 'tom')
  await userEvent.click(await screen.findByRole('button', { name: 'Retry' }))
  await waitFor(() => expect(calls(fetch, '/api/v1/movies').length).toBeGreaterThan(1))
  expect(screen.getByText('Search isn’t available right now.')).toBeInTheDocument()
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(box()).toHaveFocus()
  await userEvent.keyboard('{Escape}')
  expect(box()).not.toHaveFocus()
})

test('"/" focuses the search, but not while typing in a field', async () => {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('min-width'), media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => false }))
  api()
  await start('/about')
  await userEvent.keyboard('/')
  expect(box()).toHaveFocus()
  expect(box()).toHaveValue('')
  const field = document.createElement('input')
  document.body.append(field)
  field.focus()
  await userEvent.keyboard('a/b')
  expect(field).toHaveValue('a/b')
  field.remove()
})

test('on a phone the icon opens a full-screen search; choosing a result closes it', async () => {
  api()
  const { router } = await start('/about')
  await userEvent.click(screen.getByRole('button', { name: 'Search' }))
  const dialog = await screen.findByRole('dialog', { name: 'Search' })
  const input = within(dialog).getByRole('combobox')
  await waitFor(() => expect(input).toHaveFocus())
  await userEvent.type(input, 'tom')
  await userEvent.click(await within(dialog).findByText('Clue'))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  await waitFor(() => expect(router.state.location.pathname).toBe('/movies/15196'))
})

test('the Series page has no search', async () => {
  renderApp('/series')
  await screen.findByRole('heading', { level: 1, name: 'Series: coming soon' })
  expect(screen.queryByRole('combobox', { name: /search/i })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Search' })).toBeNull()
})
