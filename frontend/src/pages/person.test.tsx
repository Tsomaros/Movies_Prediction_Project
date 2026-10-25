import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import type { PersonDetail } from '@/api/client'
import { decodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { sortFilms } from '@/movies/people'
import { mockFetch } from '@/test/fetch'
import optionsJson from '@/test/options.json'
import personJson from '@/test/person.json'
import plainJson from '@/test/person_plain.json'
import { renderApp } from '@/test/render'

const HANKS = personJson as PersonDetail // real answers saved from the API: Tom Hanks, and Eric Roth (no TMDB details)
const PLAIN = plainJson as PersonDetail

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 25, 12))
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function serve(person: PersonDetail | null, id = person?.id ?? 424242) {
  return mockFetch({
    '/api/v1/auth/me': { body: { user: null } },
    '/api/v1/meta/options': { body: optionsJson },
    [`/api/v1/people/${id}`]: person ? { body: person } : { status: 404, body: { detail: 'Person not found' } },
  })
}

const gridTitles = () => within(screen.getByRole('list', { name: 'Films' })).getAllByRole('listitem')
  .map(li => li.querySelector('a span span')?.textContent)

describe('the person page', () => {
  test('has the photo, life dates, stats, biography, links and films with characters', async () => {
    serve(HANKS)
    renderApp('/people/31')
    expect(await screen.findByRole('heading', { level: 1, name: 'Tom Hanks' })).toBeInTheDocument()
    await waitFor(() => expect(document.title).toBe('Tom Hanks · Movie Prediction'))
    expect(screen.getByRole('img', { name: 'Photo of Tom Hanks' })).toHaveAttribute('src', HANKS.photo!.large)
    expect(screen.getByText('Born 9 Jul 1956 · 70 · Concord, California, USA')).toBeInTheDocument()
    const stats = screen.getByRole('list', { name: 'Stats' })
    expect(within(stats).getByText('85 films · 1980–2025')).toBeInTheDocument()
    expect(within(stats).getByText(/^Average score 6\.8 from 77 films$/)).toBeInTheDocument()
    expect(within(stats).getByRole('link', { name: 'Tim Allen' })).toHaveAttribute('href', `/people/${HANKS.stats.top_costar!.id}`)
    expect(within(stats).getByRole('link', { name: 'Steven Spielberg' })).toHaveAttribute('href', '/people/488')
    const elsewhere = screen.getByRole('list', { name: 'Elsewhere' })
    expect(within(elsewhere).getByRole('link', { name: /IMDb/ })).toHaveAttribute('href', HANKS.imdb_url)
    expect(within(elsewhere).getByRole('link', { name: /TMDB/ })).toHaveAttribute('href', 'https://www.themoviedb.org/person/31')
    const films = screen.getByRole('list', { name: 'Films' })
    expect(within(films).getAllByRole('listitem')).toHaveLength(85)
    const forrest = HANKS.cast_credits.find(f => f.title === 'Forrest Gump')!
    const card = within(films).getAllByRole('link').find(l => l.getAttribute('href') === `/movies/${forrest.id}`)!
    expect(card).toHaveTextContent('Forrest Gump')
    expect(within(card).getByText('as Forrest Gump')).toBeInTheDocument()
    expect(gridTitles()[0]).toBe(HANKS.cast_credits[0].title) // newest first, as the API sends them
    expect(screen.getByRole('heading', { name: 'Also directed' })).toBeInTheDocument()
  })

  test('a long biography starts clamped with Read more; the text is plain paragraphs, never HTML', async () => {
    serve({ ...HANKS, biography: `Line one.\n\n<b>Line</b> two.\n\n${'More. '.repeat(120)}` })
    renderApp('/people/31')
    const bio = await screen.findByTestId('biography')
    expect(within(bio).getByText('<b>Line</b> two.')).toBeInTheDocument()
    expect(bio.querySelector('b')).toBeNull()
    expect(bio.querySelectorAll('p')).toHaveLength(3)
    expect(bio).toHaveClass('line-clamp-4')
    await userEvent.click(screen.getByRole('button', { name: 'Read more' }))
    expect(bio).not.toHaveClass('line-clamp-4')
    expect(screen.getByRole('button', { name: 'Show less' })).toHaveAttribute('aria-expanded', 'true')
  })

  test('someone without TMDB details gets an initials avatar, only the stats there are, and their crew work', async () => {
    serve(PLAIN)
    renderApp(`/people/${PLAIN.id}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Eric Roth' })).toBeInTheDocument()
    expect(screen.getByText('ER')).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /^Photo of/ })).toBeNull()
    expect(screen.queryByTestId('biography')).toBeNull()
    expect(within(screen.getByRole('list', { name: 'Elsewhere' })).getAllByRole('link').map(a => a.textContent?.trim())).toEqual(['TMDB'])
    const stats = screen.getByRole('list', { name: 'Stats' })
    expect(within(stats).getByText('1 film · 2009')).toBeInTheDocument()
    expect(within(stats).queryByText(/box office/)).toBeNull()
    expect(within(stats).queryByText(/Most often/)).toBeNull()
    expect(screen.getByRole('heading', { name: 'Also wrote' })).toBeInTheDocument() // Screenplay and Writer together
    expect(screen.getByRole('heading', { name: 'Also produced' })).toBeInTheDocument()
  })

  test('a director with no acting credits has no films grid and no predict button', async () => {
    const director = { ...PLAIN, cast_credits: [], stats: { ...PLAIN.stats, film_count: 0, first_year: null, last_year: null, top_genres: [], avg_score: null } }
    serve(director)
    renderApp(`/people/${PLAIN.id}`)
    expect(await screen.findByRole('heading', { name: 'Wrote' })).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Films' })).toBeNull()
    expect(screen.queryByRole('list', { name: 'Stats' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Predict a film with this actor' })).toBeNull()
  })

  test('the sort is kept in the URL', async () => {
    serve(HANKS)
    const { router } = renderApp('/people/31')
    await userEvent.click(await screen.findByRole('combobox', { name: 'Sort films' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Highest score' }))
    expect(router.state.location.search).toBe('?sort=score')
    expect(gridTitles()[0]).toBe('The Green Mile')
  })

  test('the film order: oldest, score and box office put films without the value last', () => {
    const f = (id: number, release_date: string | null, score: number | null, votes: number, revenue_2025: number | null) =>
      ({ ...HANKS.cast_credits[0], id, release_date, score, votes, revenue_2025 })
    const films = [f(1, '2001-01-01', 7, 100, null), f(2, null, 9, 100, 5e8), f(3, '1990-01-01', null, 0, 1e9)]
    expect(sortFilms(films, 'oldest').map(x => x.id)).toEqual([3, 1, 2])
    expect(sortFilms(films, 'score').map(x => x.id)).toEqual([2, 1, 3])
    expect(sortFilms(films, 'box_office').map(x => x.id)).toEqual([3, 2, 1])
    expect(sortFilms(films, 'newest')).toBe(films)
  })

  test('an odd sort in the link falls back to newest first', async () => {
    serve(HANKS)
    renderApp('/people/31?sort=nonsense')
    await screen.findByRole('heading', { level: 1, name: 'Tom Hanks' })
    expect(gridTitles()[0]).toBe(HANKS.cast_credits[0].title)
  })

  test('"Predict a film with this actor" opens the form with them as the lead', async () => {
    serve(HANKS)
    const { router } = renderApp('/people/31')
    await userEvent.click(await screen.findByRole('button', { name: 'Predict a film with this actor' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/predict'))
    const params = new URLSearchParams(router.state.location.search)
    expect(decodeForm(params.get(URL_PARAM))?.actors).toEqual([{ id: 31, name: 'Tom Hanks' }])
    expect(params.get(LIKE_PARAM)).toBe('Tom Hanks')
  })

  test('an unknown person, or an id that is not a number, gets the not-found page', async () => {
    serve(null)
    renderApp('/people/424242')
    expect(await screen.findByRole('heading', { name: "We don't have this person" })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Search films and people' })).toHaveAttribute('href', '/browse')
  })

  test('an id that is not a number never asks the API', async () => {
    const { calls } = serve(null)
    renderApp('/people/abc')
    expect(await screen.findByRole('heading', { name: "We don't have this person" })).toBeInTheDocument()
    expect(calls.some(c => c.url.pathname.startsWith('/api/v1/people'))).toBe(false)
  })

  test('a server error offers Try again', async () => {
    mockFetch({ '/api/v1/auth/me': { body: { user: null } }, '/api/v1/people/31': { status: 500, body: {} } })
    renderApp('/people/31')
    expect(await screen.findByRole('button', { name: 'Try again' }, { timeout: 4000 })).toBeInTheDocument()
  })
})
