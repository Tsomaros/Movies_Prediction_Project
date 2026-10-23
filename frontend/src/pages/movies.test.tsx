import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { ModelCard, MovieDetail, MovieList, Options } from '@/api/client'
import { decodeForm, LIKE_PARAM } from '@/form/persist'
import { browseLink, EMPTY, pageNumbers, readBrowse, VIEW_KEY, writeBrowse } from '@/movies/browse'
import { crewByJob, initials, nameHue, runtimeText } from '@/movies/people'
import { filmToForm } from '@/movies/predictLike'
import { ROWS } from '@/movies/rows'
import { SEARCH_MS } from '@/pages/Movies'
import { mockFetch } from '@/test/fetch'
import modelCardJson from '@/test/model_card.json'
import movieJson from '@/test/movie.json'
import moviesJson from '@/test/movies.json'
import optionsJson from '@/test/options.json'
import { renderApp } from '@/test/render'

const options = optionsJson as Options
const LIST = moviesJson as MovieList
const FILM = movieJson as MovieDetail

afterEach(() => vi.unstubAllGlobals())

function serve(list: (url: URL) => MovieList = () => LIST, film: MovieDetail | null = FILM) {
  return mockFetch({
    '/api/v1/meta/options': { body: options },
    '/api/v1/model-card': { body: modelCardJson as ModelCard },
    '/api/v1/movies': url => ({ body: list(url) }),
    [`/api/v1/movies/${FILM.id}`]: film ? { body: film } : { status: 404, body: { detail: 'No film' } },
  })
}
const movieCalls = (calls: ReturnType<typeof serve>['calls']) => calls.filter(c => c.url.pathname === '/api/v1/movies')
const lastQuery = (calls: ReturnType<typeof serve>['calls']) => Object.fromEntries(movieCalls(calls).at(-1)!.url.searchParams)

describe('the browse state in the URL', () => {
  test('round-trips, leaves defaults out and drops anything malformed', () => {
    const state = { ...EMPTY, q: 'alien', genre: 'Horror', yearFrom: 1979, yearTo: 1990, language: 'en', scoreMin: 7, sort: 'newest' as const, page: 3 }
    expect(readBrowse(writeBrowse(state))).toEqual(state)
    expect(writeBrowse(EMPTY).toString()).toBe('')
    expect(readBrowse(new URLSearchParams('from=abc&to=99999&lang=ENG&score=11&sort=evil&page=-2'))).toEqual(EMPTY)
    expect(browseLink({ sort: 'revenue' })).toBe('/movies?sort=revenue')
  })

  test('the pager shows the ends, the neighbours and gaps', () => {
    expect(pageNumbers(7, 20)).toEqual([1, null, 6, 7, 8, null, 20])
    expect(pageNumbers(1, 3)).toEqual([1, 2, 3])
    expect(pageNumbers(3, 5)).toEqual([1, 2, 3, 4, 5]) // a one-page gap shows the page
  })
})

describe('people and facts', () => {
  test('initials skip suffixes, colours are stable per name', () => {
    expect([initials('Robert Downey Jr.'), initials('Zendaya'), initials('  '), initials('Élodie Bouchez')]).toEqual(['RD', 'Z', '?', 'ÉB'])
    expect(nameHue('Chris Evans')).toBe(nameHue('Chris Evans'))
    expect(nameHue('Chris Evans')).not.toBe(nameHue('Chris Pratt'))
  })

  test('runtime and crew text', () => {
    expect([runtimeText(149), runtimeText(120), runtimeText(45)]).toEqual(['2 h 29 min', '2 h', '45 min'])
    expect(crewByJob(FILM.crew, ['Director', 'Editor'])).toEqual([
      { job: 'Director', names: ['Anthony Russo', 'Joe Russo'] }, { job: 'Editor', names: ['Jeffrey Ford', 'Matthew Schmidt'] }])
  })
})

describe('"Predict a film like this"', () => {
  test('carries genres, themes, runtime, language, rating, director and the top-billed cast; the date is a new film\'s', () => {
    const form = filmToForm(FILM, options, new Date(2026, 9, 23))
    expect(form.genres).toEqual(['Adventure', 'Action', 'Science Fiction'])
    expect(form.themes).toEqual(FILM.themes.slice(0, 5))
    expect([form.runtime, form.language, form.certification]).toEqual([149, 'en', 'PG-13'])
    expect(form.director).toEqual({ id: 19271, name: 'Anthony Russo' })
    expect(form.actors.map(a => a.name)).toEqual(['Robert Downey Jr.', 'Chris Evans', 'Chris Hemsworth', 'Josh Brolin', 'Mark Ruffalo'])
    expect([form.release_year, form.release_month, form.budget, form.franchise, form.companies]).toEqual([2027, 6, null, null, []])
  })

  test('values the form would refuse are left out or reset', () => {
    const odd = { ...FILM, genres: ['Action', 'Cartoon'], runtime: 12, certification: 'NR', original_language: null, crew: [], cast: [] }
    const form = filmToForm(odd as MovieDetail, options)
    expect([form.genres, form.runtime, form.certification, form.language, form.director, form.actors])
      .toEqual([['Action'], 110, 'unrated/unknown', 'en', null, []])
    expect(filmToForm({ ...FILM, certification: null }, options).certification).toBe('') // left for the creator
  })

  test('the button opens the form filled in, saying which film it started from', async () => {
    serve()
    const { router } = renderApp(`/movies/${FILM.id}`)
    await userEvent.click(await screen.findByRole('button', { name: /Predict a film like this/ }))
    expect(await screen.findByTestId('like-hint')).toHaveTextContent('Started from Avengers: Infinity War')
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get(LIKE_PARAM)).toBe('Avengers: Infinity War')
    expect(decodeForm(params.get('f'))).toEqual(filmToForm(FILM, options))
    expect(screen.getByRole('button', { name: 'Remove Anthony Russo' })).toBeInTheDocument()
  })
})

describe('the browse page', () => {
  test('shows a page of films with score and votes, and the pager', async () => {
    serve()
    renderApp('/movies')
    const grid = await screen.findByRole('list', { name: 'Films' })
    expect(within(grid).getAllByRole('link')).toHaveLength(24)
    expect(within(grid).getAllByRole('link')[0]).toHaveAttribute('href', `/movies/${LIST.items[0].id}`)
    expect(grid).toHaveTextContent(`(${LIST.items[0].votes.toLocaleString('en-US')} votes)`)
    expect(screen.getByText(/79,199 films · page 1 of 3,300/)).toBeInTheDocument()
    const pager = screen.getByRole('navigation', { name: 'Pages' })
    expect(within(pager).getByRole('link', { name: 'Page 1' })).toHaveAttribute('aria-current', 'page')
    expect(within(pager).getByRole('link', { name: 'Next page' })).toHaveAttribute('href', '/movies?page=2')
  })

  test('the search box writes ?q= 300 ms after typing stops and starts from page 1', async () => {
    const { calls } = serve()
    const { router } = renderApp('/movies?page=4')
    await screen.findByRole('list', { name: 'Films' })
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search films' }), 'alien')
    await waitFor(() => expect(router.state.location.search).toBe('?q=alien'), { timeout: SEARCH_MS + 1000 })
    await waitFor(() => expect(lastQuery(calls)).toMatchObject({ q: 'alien', page: '1' }))
    expect(movieCalls(calls).filter(c => c.url.searchParams.get('q')?.startsWith('ali')).length).toBe(1) // not per keystroke
  })

  test('filters and sort go to the URL and the request; chips remove them', async () => {
    const { calls } = serve()
    const { router } = renderApp('/movies?page=2')
    await screen.findByRole('list', { name: 'Films' })
    const side = screen.getByRole('complementary', { name: 'Filter films' })
    await userEvent.selectOptions(within(side).getByLabelText('Genre'), 'Horror')
    await userEvent.selectOptions(within(side).getByLabelText('Audience score'), '7')
    const from = within(side).getByLabelText('From year')
    await userEvent.type(from, '1980{Enter}')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'newest')
    expect(readBrowse(new URLSearchParams(router.state.location.search)))
      .toEqual({ ...EMPTY, genre: 'Horror', scoreMin: 7, yearFrom: 1980, sort: 'newest', page: 1 })
    await waitFor(() => expect(lastQuery(calls)).toMatchObject({ genre: 'Horror', score_min: '7', year_from: '1980', sort: 'newest' }))
    await userEvent.click(screen.getByRole('button', { name: 'Remove filter Horror' }))
    expect(new URLSearchParams(router.state.location.search).get('genre')).toBeNull()
  })

  test('no results: a button per filter and "Clear all"', async () => {
    serve(() => ({ items: [], total: 0, page: 1, page_size: 24, pages: 0 }))
    const { router } = renderApp('/movies?genre=Western&lang=ja&q=zzz')
    const none = await screen.findByTestId('no-results')
    expect(within(none).getAllByRole('button')).toHaveLength(4)
    await userEvent.click(within(none).getByRole('button', { name: 'Remove Western' }))
    expect(router.state.location.search).toBe('?q=zzz&lang=ja')
    await userEvent.click(within(await screen.findByTestId('no-results')).getByRole('button', { name: 'Clear all' }))
    expect(router.state.location.search).toBe('')
  })

  test('the poster size or list view is remembered', async () => {
    serve()
    renderApp('/movies')
    await screen.findByRole('list', { name: 'Films' })
    await userEvent.click(screen.getByRole('radio', { name: 'List' }))
    expect(localStorage.getItem(VIEW_KEY)).toBe('list')
    expect(screen.getByRole('radio', { name: 'List' })).toHaveAttribute('aria-checked', 'true')
    expect(within(screen.getByRole('list', { name: 'Films' })).getAllByText(/Drama|Comedy|Horror|Action|Adventure/).length).toBeGreaterThan(0)
  })

  test('a failed load offers a retry', async () => {
    mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/movies': new TypeError('offline') })
    renderApp('/movies')
    expect(await screen.findByRole('alert')).toHaveTextContent("The films couldn't load")
  })
})

describe('the film page', () => {
  test('facts, score with votes, cast with initials, key crew, similar films and the TMDB link', async () => {
    serve()
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Avengers: Infinity War (2018)' })).toBeInTheDocument()
    await waitFor(() => expect(document.title).toBe('Avengers: Infinity War (2018) · Movie Prediction'))
    expect(screen.getByText('PG-13 · 2 h 29 min · 2018-04-25 · English')).toBeInTheDocument()
    expect(screen.getByTestId('film-score')).toHaveTextContent('8.2(33,200 votes)')
    const cast = screen.getByRole('region', { name: 'Cast' })
    expect(within(cast).getByText('RD')).toBeInTheDocument()
    expect(within(cast).getByText('Tony Stark / Iron Man')).toBeInTheDocument()
    expect(screen.getByText('Anthony Russo, Joe Russo')).toBeInTheDocument()
    const similar = screen.getByRole('region', { name: 'Similar films' })
    expect(within(similar).getAllByRole('link')[0]).toHaveAttribute('href', `/movies/${FILM.similar[0].id}`)
    expect(screen.getByRole('link', { name: /This film on TMDB/ })).toHaveAttribute('href', 'https://www.themoviedb.org/movie/299536')
  })

  test('money switches between reported and 2025 dollars', async () => {
    serve()
    renderApp(`/movies/${FILM.id}`)
    const panel = await screen.findByRole('region', { name: 'Money' })
    expect(panel).toHaveTextContent('Budget$380M') // 2025 dollars first
    await userEvent.click(within(panel).getByRole('radio', { name: 'As reported' }))
    expect(panel).toHaveTextContent('Budget$300M')
    expect(panel).toHaveTextContent('Worldwide box office$2.1B')
  })

  test('a film with few votes, no poster and no money says so', async () => {
    serve(undefined, { ...FILM, poster: null, rating: { average: 9.4, votes: 12, usable: false },
      money: { ...FILM.money, budget: null, revenue: null, budget_2025: null, revenue_2025: null } })
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByTestId('film-score')).toHaveTextContent('9.4(12 votes) · fewer than 50 votes')
    expect(screen.getByRole('img', { name: 'No poster for Avengers: Infinity War' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Money' })).getAllByText('not reported')).toHaveLength(2)
  })

  test('an unknown film is a 404 page with search and home links', async () => {
    serve(undefined, null)
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByRole('heading', { name: "We don't have this film" })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Search films' })).toHaveAttribute('href', '/movies')
    renderApp('/movies/not-a-number')
    await waitFor(() => expect(screen.getAllByRole('heading', { name: "We don't have this film" })).toHaveLength(2))
  })
})

describe('the home page and attribution', () => {
  test('the curated rows come from the config, each with "See all" on the same query', async () => {
    serve()
    renderApp('/')
    for (const row of ROWS) {
      const section = await screen.findByTestId(`row-${row.key}`)
      expect(within(section).getByRole('heading', { name: row.title })).toBeInTheDocument()
      expect(within(section).getByRole('link', { name: /See all/ })).toHaveAttribute('href', browseLink(row.filters))
    }
    await waitFor(() => expect(within(screen.getByTestId('row-popular')).getAllByRole('link').length).toBeGreaterThan(6))
  })

  test.each(['/', '/predict', '/predict/result', '/movies', `/movies/${FILM.id}`, '/about', '/no/such/page'])(
    '%s carries the TMDB logo and notice', async path => {
      serve()
      renderApp(path)
      const footer = await screen.findByTestId('tmdb-attribution')
      expect(within(footer).getByRole('img', { name: 'TMDB' })).toHaveAttribute('src', '/tmdb-logo.svg')
      expect(within(footer).getByRole('link')).toHaveAttribute('href', 'https://www.themoviedb.org')
      expect(footer).toHaveTextContent('This product uses the TMDB API but is not endorsed or certified by TMDB.')
    })

  test('the About page shows the served models\' accuracy and links to the code', async () => {
    serve()
    renderApp('/about')
    expect(await screen.findByRole('heading', { level: 1, name: 'About' })).toBeInTheDocument()
    expect(await screen.findByTestId('accuracy')).toHaveTextContent('77% of 1,485')
    expect(screen.getByRole('link', { name: 'GitHub' })).toHaveAttribute('href', 'https://github.com/Tsomaros/Movies_Prediction_Project')
  })
})
