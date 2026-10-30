import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { CareerModelResponse, ModelCard, MovieDetail, MovieList, Options, Recipe } from '@/api/client'
import { emptyForm } from '@/form/model'
import { decodeForm, LIKE_PARAM } from '@/form/persist'
import { browseLink, browseResets, EMPTY, pageNumbers, readBrowse, VIEW_KEY, writeBrowse } from '@/movies/browse'
import { crewByJob, formatLife, initials, nameHue, runtimeText } from '@/movies/people'
import { filmToForm, personToForm, recipeToForm } from '@/movies/predictLike'
import { localToday } from '@/movies/release'
import { ROWS } from '@/movies/rows'
import hanksModelJson from '@/test/career_hanks_model.json'
import nolanModelJson from '@/test/career_nolan_model.json'
import { mockFetch } from '@/test/fetch'
import modelCardJson from '@/test/model_card.json'
import movieJson from '@/test/movie.json'
import moviesJson from '@/test/movies.json'
import optionsJson from '@/test/options.json'
import peopleSearchJson from '@/test/people_search_hanks.json'
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
/** Open a menu (the form's Radix Select) and pick the option with this text. */
async function choose(trigger: HTMLElement, option: string) {
  await userEvent.click(trigger)
  await userEvent.click(await screen.findByRole('option', { name: option }))
}
const movieCalls = (calls: ReturnType<typeof serve>['calls']) => calls.filter(c => c.url.pathname === '/api/v1/movies')
const lastQuery = (calls: ReturnType<typeof serve>['calls']) => Object.fromEntries(movieCalls(calls).at(-1)!.url.searchParams)

describe('the browse state in the URL', () => {
  test('round-trips, leaves defaults out and drops anything malformed', () => {
    const state = { ...EMPTY, q: 'alien', genre: 'Horror', yearFrom: 1979, yearTo: 1990, language: 'en', scoreMin: 7, sort: 'newest' as const, page: 3 }
    expect(readBrowse(writeBrowse(state))).toEqual(state)
    expect(writeBrowse(EMPTY).toString()).toBe('')
    expect(readBrowse(new URLSearchParams('from=abc&to=99999&lang=ENG&score=11&sort=evil&page=-2'))).toEqual(EMPTY)
    expect(browseLink({ sort: 'revenue' })).toBe('/browse?sort=revenue')
  })

  test('when round-trips through the URL, the soonest sort is known and bad values reset', () => {
    expect(readBrowse(new URLSearchParams('when=upcoming&sort=soonest'))).toMatchObject({ when: 'upcoming', sort: 'soonest' })
    expect(readBrowse(new URLSearchParams('when=later')).when).toBeNull()
    expect(browseResets(new URLSearchParams('when=later'), undefined)).toContain('released or upcoming')
    expect(browseResets(new URLSearchParams('when=released&sort=newest'), undefined)).toEqual([])
    expect(browseLink({ when: 'released', sort: 'newest' })).toBe('/browse?when=released&sort=newest')
    expect(writeBrowse({ ...EMPTY, when: 'upcoming', sort: 'soonest' }).toString()).toBe('when=upcoming&sort=soonest')
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
    const names = crewByJob(FILM.crew, ['Director', 'Editor']).map(g => ({ job: g.job, names: g.people.map(p => p.name) }))
    expect(names).toEqual([
      { job: 'Director', names: ['Anthony Russo', 'Joe Russo'] }, { job: 'Editor', names: ['Jeffrey Ford', 'Matthew Schmidt'] }])
    expect(crewByJob(FILM.crew, ['Director'])[0].people[0]).toEqual(
      { id: FILM.crew.find(c => c.name === 'Anthony Russo')!.id, name: 'Anthony Russo' })
  })

  test('life dates: a birthday with the age, a lifespan, a death year, or nothing', () => {
    const today = new Date(2026, 9, 25)
    expect(formatLife('1956-07-09', null, today)).toBe('Born 9 Jul 1956 · 70')
    expect(formatLife('1956-10-26', null, today)).toBe('Born 26 Oct 1956 · 69') // the birthday is tomorrow
    expect(formatLife('1956-10-25', null, today)).toBe('Born 25 Oct 1956 · 70')
    expect(formatLife('1920-01-01', '1990-06-01', today)).toBe('1920–1990')
    expect(formatLife(null, '1990-06-01', today)).toBe('Died 1990')
    expect(formatLife(null, null, today)).toBeNull()
    expect(formatLife('not a date', undefined, today)).toBeNull()
  })

  test('"Predict a film with this actor / director" starts a fresh form with them in that slot', () => {
    const director = personToForm({ id: 525, name: 'Christopher Nolan' }, 'director', new Date(2026, 9, 25))
    expect(director).toEqual({ ...emptyForm(new Date(2026, 9, 25)), director: { id: 525, name: 'Christopher Nolan' } })
    const form = personToForm({ id: 31, name: 'Tom Hanks' }, 'actor', new Date(2026, 9, 25))
    expect(form.actors).toEqual([{ id: 31, name: 'Tom Hanks' }])
    expect(form).toEqual({ ...emptyForm(new Date(2026, 9, 25)), actors: [{ id: 31, name: 'Tom Hanks' }] })
    expect(form.director).toBeNull()
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

describe('"Edit in predictor" (the Career section model films)', () => {
  // Real answers: Tom Hanks's usual film (named director and co-stars) and Christopher Nolan's "Something new"
  // (every actor slot "new")
  const HANKS = hanksModelJson as CareerModelResponse
  const NOLAN = nolanModelJson as CareerModelResponse
  const today = new Date(2026, 9, 25)

  test('the usual film carries every recipe field, named people with their ids and the median budget', () => {
    const form = recipeToForm(HANKS.usual!.recipe, options, today)
    expect(form).toEqual({
      ...emptyForm(today),
      genres: ['Drama', 'Documentary'], themes: ['history and war', 'true story', 'science fiction'],
      runtime: 105, language: 'en', certification: 'PG-13', release_year: 2027, release_month: 6,
      director: { id: 24, name: 'Robert Zemeckis' },
      actors: [{ id: 31, name: 'Tom Hanks' }, { id: 12898, name: 'Tim Allen' }, { id: 12900, name: 'Wallace Shawn' }],
      countries: ['US'], budget: 41079286,
    })
  })

  test('"new" slots are left empty for the creator to name', () => {
    const form = recipeToForm(NOLAN.new.recipe, options, today)
    expect([form.genres, form.director, form.actors]).toEqual([['Comedy', 'Romance'], { id: 525, name: 'Christopher Nolan' }, []])
    expect(recipeToForm(HANKS.new.recipe, options, today).director).toBeNull()
  })

  test('values the form would refuse are left out or reset', () => {
    const odd: Recipe = { ...HANKS.usual!.recipe, runtime: 12, certification: 'XX', country: null, budget_2025: null,
      themes: ['history and war', 'not a theme'], director: { id: 24, name: null },
      labels: { ...HANKS.usual!.recipe.labels, genres: ['Drama', 'Cartoon'] } }
    const form = recipeToForm(odd, options, today)
    expect([form.genres, form.themes, form.runtime, form.certification, form.countries, form.budget, form.director])
      .toEqual([['Drama'], ['history and war'], 110, '', [], null, null])
  })
})

describe('the browse page', () => {
  test('shows a page of films with score and votes, and the pager', async () => {
    serve()
    renderApp('/browse')
    const grid = await screen.findByRole('list', { name: 'Films' })
    expect(within(grid).getAllByRole('link')).toHaveLength(24)
    expect(within(grid).getAllByRole('link')[0]).toHaveAttribute('href', `/movies/${LIST.items[0].id}`)
    expect(grid).toHaveTextContent(`(${LIST.items[0].votes.toLocaleString('en-US')} votes)`)
    expect(screen.getByText(/79,199 films · page 1 of 3,300/)).toBeInTheDocument()
    const pager = screen.getByRole('navigation', { name: 'Pages' })
    expect(within(pager).getByRole('link', { name: 'Page 1' })).toHaveAttribute('aria-current', 'page')
    expect(within(pager).getByRole('link', { name: 'Next page' })).toHaveAttribute('href', '/browse?page=2')
  })

  test('a search from the URL is asked for, and its chip removes it but keeps the filters', async () => {
    const { calls } = serve()
    const { router } = renderApp('/browse?q=tom&genre=Drama&page=2')
    await screen.findByRole('list', { name: 'Films' })
    expect(lastQuery(calls)).toMatchObject({ q: 'tom', genre: 'Drama', page: '2' })
    expect(screen.getByText(/Results for/)).toHaveTextContent('Results for ‘tom’')
    expect(screen.queryByRole('button', { name: /Remove filter .tom/ })).toBeNull() // the search isn't a filter chip
    await userEvent.click(screen.getByRole('button', { name: 'Remove search ‘tom’' }))
    expect(router.state.location.search).toBe('?genre=Drama')
  })

  test('the page has no search box or people row of its own', async () => {
    serve()
    renderApp('/browse?q=tom')
    await screen.findByRole('list', { name: 'Films' })
    expect(screen.queryByRole('searchbox', { name: 'Search films' })).toBeNull()
    expect(screen.queryByTestId('people-row')).toBeNull()
    expect(screen.getAllByRole('combobox', { name: 'Search movies' })).toHaveLength(1) // the header's
  })

  test('filters and sort go to the URL and the request; chips remove them', async () => {
    const { calls } = serve()
    const { router } = renderApp('/browse?page=2')
    await screen.findByRole('list', { name: 'Films' })
    const side = screen.getByRole('complementary', { name: 'Filter films' })
    await choose(within(side).getByLabelText('Genre'), 'Horror')
    await choose(within(side).getByLabelText('Audience score'), '7+ (any number of votes)')
    const from = within(side).getByLabelText('From year')
    await userEvent.type(from, '1980{Enter}')
    await choose(screen.getByRole('combobox', { name: 'Sort by' }), 'Newest')
    expect(readBrowse(new URLSearchParams(router.state.location.search)))
      .toEqual({ ...EMPTY, genre: 'Horror', scoreMin: 7, yearFrom: 1980, sort: 'newest', page: 1 })
    await waitFor(() => expect(lastQuery(calls)).toMatchObject({ genre: 'Horror', score_min: '7', year_from: '1980', sort: 'newest' }))
    await userEvent.click(screen.getByRole('button', { name: 'Remove filter Horror' }))
    expect(new URLSearchParams(router.state.location.search).get('genre')).toBeNull()
  })

  test('no results: a button per filter, "Clear filters" (the search stays) and the people who match', async () => {
    const fetch = mockFetch({
      '/api/v1/meta/options': { body: options },
      '/api/v1/movies': url => ({ body: { items: [], total: 0, page: 1, page_size: Number(url.searchParams.get('page_size') ?? 24), pages: 0 } }),
      '/api/v1/people/search': { body: { ...peopleSearchJson, total: 1 } },
    })
    const { router } = renderApp('/browse?genre=Western&lang=ja&q=tom%20hanks')
    const none = await screen.findByTestId('no-results')
    expect(within(none).getByText('No movies match ‘tom hanks’.')).toBeInTheDocument()
    expect(await within(none).findByRole('link', { name: /1 person found/ })).toHaveAttribute('href', '/people?q=tom%20hanks')
    expect(fetch.calls.find(c => c.url.pathname === '/api/v1/people/search')!.url.search).toBe('?q=tom+hanks&page_size=1')
    expect(within(none).getAllByRole('button')).toHaveLength(3)
    await userEvent.click(within(none).getByRole('button', { name: 'Remove Western' }))
    expect(router.state.location.search).toBe('?q=tom+hanks&lang=ja')
    await userEvent.click(within(await screen.findByTestId('no-results')).getByRole('button', { name: 'Clear filters' }))
    expect(router.state.location.search).toBe('?q=tom+hanks')
  })

  test('the poster size or list view is remembered', async () => {
    serve()
    renderApp('/browse')
    await screen.findByRole('list', { name: 'Films' })
    await userEvent.click(screen.getByRole('radio', { name: 'List' }))
    expect(localStorage.getItem(VIEW_KEY)).toBe('list')
    expect(screen.getByRole('radio', { name: 'List' })).toHaveAttribute('aria-checked', 'true')
    expect(within(screen.getByRole('list', { name: 'Films' })).getAllByText(/Drama|Comedy|Horror|Action|Adventure/).length).toBeGreaterThan(0)
  })

  test('a failed load offers a retry', async () => {
    mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/movies': new TypeError('offline') })
    renderApp('/browse')
    expect(await screen.findByRole('alert')).toHaveTextContent("The films couldn't load")
  })
})

describe('the browse page: the release window', () => {
  test('a Coming soon chip, asked of the API with when, and removable', async () => {
    const { calls } = serve()
    renderApp('/browse?when=upcoming&sort=soonest')
    const chip = await screen.findByRole('button', { name: /remove filter coming soon/i })
    expect(chip).toBeInTheDocument()
    await waitFor(() => expect(lastQuery(calls)).toMatchObject({ when: 'upcoming', sort: 'soonest' }))
    await userEvent.click(chip)
    await waitFor(() => expect(lastQuery(calls)).not.toHaveProperty('when'))
  })

  test('the Release menu sets and clears the window', async () => {
    const { calls } = serve()
    renderApp('/browse')
    await screen.findAllByRole('link', { name: /poster/i })
    await choose(screen.getAllByRole('combobox', { name: /release/i })[0], 'Just released')
    await waitFor(() => expect(lastQuery(calls)).toMatchObject({ when: 'released' }))
    expect(await screen.findByRole('button', { name: /remove filter just released/i })).toBeInTheDocument()
  })
})

describe('cast photos on the film page', () => {
  test('a cast member with a TMDB photo shows it; one without keeps the initials', async () => {
    const photo = { small: 'https://image.tmdb.org/t/p/w185/rdj.jpg', large: 'https://image.tmdb.org/t/p/h632/rdj.jpg' }
    serve(undefined, { ...FILM, cast: FILM.cast.map((c, i) => (i === 0 ? { ...c, photo } : c)) })
    renderApp(`/movies/${FILM.id}`)
    const cast = await screen.findByRole('region', { name: 'Cast' })
    const items = within(cast).getAllByRole('listitem')
    expect(items[0].querySelector('img')).toHaveAttribute('src', photo.small)
    expect(within(items[1]).getByText(initials(FILM.cast[1].name!))).toBeInTheDocument()
    expect(items[1].querySelector('img')).toBeNull()
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
    const rdj = FILM.cast.find(c => c.name === 'Robert Downey Jr.')!
    expect(cast.querySelectorAll('img')).toHaveLength(0) // the saved answer predates photos: initials for everyone
    expect(within(cast).getByRole('link', { name: 'Robert Downey Jr.' })).toHaveAttribute('href', `/people/${rdj.id}`)
    const made = screen.getByRole('region', { name: 'Made by' })
    const directors = within(made).getByText('Anthony Russo').closest('dd')!
    expect(directors).toHaveTextContent('Anthony Russo, Joe Russo')
    const russo = FILM.crew.find(c => c.name === 'Joe Russo')!
    expect(within(directors).getByRole('link', { name: 'Joe Russo' })).toHaveAttribute('href', `/people/${russo.id}`)
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

  test('an unknown film is a 404 page with search and start page links', async () => {
    serve(undefined, null)
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByRole('heading', { name: "We don't have this film" })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Search films' })).toHaveAttribute('href', '/browse')
    renderApp('/movies/not-a-number')
    await waitFor(() => expect(screen.getAllByRole('heading', { name: "We don't have this film" })).toHaveLength(2))
  })
})

const daysFromNow = (n: number) => localToday(new Date(Date.now() + n * 86_400_000))

describe('new and upcoming films (V1.2)', () => {
  test('the film page of a new release: a label, and a new face without a link', async () => {
    const known = FILM.cast[0]
    serve(undefined, { ...FILM, release_date: daysFromNow(-3),
      cast: [known, { id: 990001, name: 'New Face', character: 'Friend', order: 99, photo: null, linked: false }],
      crew: [{ id: 990002, name: 'Fresh Writer', job: 'Writer', linked: false }, ...FILM.crew.filter(c => c.job === 'Director')] })
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByTestId('release-label')).toHaveTextContent('New release')
    const cast = screen.getByRole('region', { name: 'Cast' })
    expect(within(cast).getByRole('link', { name: known.name! })).toBeInTheDocument()
    expect(within(cast).getByText('New Face')).toBeInTheDocument()
    expect(within(cast).queryByRole('link', { name: 'New Face' })).toBeNull()
    expect(screen.getByText('Fresh Writer')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Fresh Writer' })).toBeNull()
    expect(screen.getByRole('region', { name: 'Money' })).toBeInTheDocument() // a released film still has its money panel
  })

  test('a coming-soon film page has its date label and no score or money', async () => {
    serve(undefined, { ...FILM, release_date: '2099-11-20', rating: { average: null, votes: 0, usable: false } })
    renderApp(`/movies/${FILM.id}`)
    expect(await screen.findByTestId('release-label')).toHaveTextContent('Coming 20 Nov 2099')
    expect(screen.getByTestId('film-score')).toHaveTextContent('Not out yet')
    expect(screen.queryByRole('region', { name: 'Money' })).toBeNull()
  })

  test('cards: New tag and Not rated yet, Coming date instead of the score, old films unchanged', async () => {
    const base = LIST.items[0]
    const items = [
      { ...base, id: 1, title: 'Fresh Hit', release_date: daysFromNow(-2), votes: 12, score: 7.1, score_ok: false },
      { ...base, id: 2, title: 'Rated New', release_date: daysFromNow(-1), votes: 900, score: 7.9, score_ok: true },
      { ...base, id: 3, title: 'Later On', release_date: '2099-03-04', votes: 0, score: null, score_ok: false },
      { ...base, id: 4, title: 'Old Classic', release_date: '1999-03-31', votes: 5000, score: 8.7, score_ok: true },
    ]
    serve(() => ({ ...LIST, items, total: 4, pages: 1 }))
    renderApp('/browse')
    const films = await screen.findByRole('list', { name: 'Films' })
    const card = (title: string) => within(films).getByText(title).closest('li')!
    expect(within(card('Fresh Hit')).getByText('New')).toBeInTheDocument()
    expect(within(card('Fresh Hit')).getByText('Not rated yet')).toBeInTheDocument()
    expect(within(card('Rated New')).getByText('New')).toBeInTheDocument()
    expect(within(card('Rated New')).getByText('7.9')).toBeInTheDocument()
    expect(within(card('Later On')).getByText('Coming 4 Mar 2099')).toBeInTheDocument()
    expect(within(card('Later On')).queryByText('No votes yet')).toBeNull()
    expect(within(card('Old Classic')).queryByText('New')).toBeNull()
    expect(within(card('Old Classic')).getByText('8.7')).toBeInTheDocument()
  })
})

describe('the curated rows and attribution', () => {
  test('the curated rows come from the config, each with "See all" on the same query', async () => {
    serve()
    renderApp('/movies')
    for (const row of ROWS) {
      const section = await screen.findByTestId(`row-${row.key}`)
      expect(within(section).getByRole('heading', { name: row.title })).toBeInTheDocument()
      expect(within(section).getByRole('link', { name: /See all/ })).toHaveAttribute('href', browseLink(row.filters))
    }
    await waitFor(() => expect(within(screen.getByTestId('row-popular')).getAllByRole('link').length).toBeGreaterThan(6))
  })

  test('/movies has the rows and Browse the filters, neither a search box of its own', async () => {
    serve()
    renderApp('/movies')
    expect(await screen.findByRole('heading', { level: 1, name: 'Movies' })).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    renderApp('/browse')
    expect(await screen.findByRole('complementary', { name: 'Filter films' }, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
    expect(screen.getAllByTestId('row-popular')).toHaveLength(1)
  })

  test.each(['?q=alien', '?genre=Horror&page=2', '?sort=newest'])('an old link /movies%s opens /browse with the same search', async query => {
    serve()
    const { router } = renderApp(`/movies${query}`)
    await waitFor(() => expect(router.state.location.pathname).toBe('/browse'))
    expect(router.state.location.search).toBe(query)
    expect(await screen.findByRole('list', { name: 'Films' })).toBeInTheDocument()
  })

  test.each(['/', '/series', '/predict', '/predict/result', '/movies', '/browse', `/movies/${FILM.id}`, '/about', '/no/such/page'])(
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
