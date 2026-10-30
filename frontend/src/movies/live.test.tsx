// The live new and upcoming films (V1.2): the rows on /movies and /browse, the card, the quick view and ?film=, the
// /new-and-upcoming page and the live matches in the header search and on the browse results. Answers are the API's
// shape (src/test/live.json, movies.json); the network is a fake fetch.
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { LiveMovie, MovieList, NewAndUpcoming, Options } from '@/api/client'
import { decodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { footerLabel, releaseLine, shortDate, statusBadge, updatedAgo } from '@/lib/live'
import { liveToForm } from '@/movies/predictLike'
import { mockFetch } from '@/test/fetch'
import liveJson from '@/test/live.json'
import moviesJson from '@/test/movies.json'
import optionsJson from '@/test/options.json'
import { renderApp } from '@/test/render'

const LIVE = liveJson as NewAndUpcoming
const FILMS = moviesJson as MovieList
const options = optionsJson as Options
const TRAIN = LIVE.new[0] // out today, not in our database
const DUNE = LIVE.upcoming[0]
const HERE = LIVE.new.find(f => f.movie_id !== null)!

afterEach(() => vi.unstubAllGlobals())

function serve({ live = LIVE as NewAndUpcoming | 'error', list = FILMS, pending = false } = {}) {
  return mockFetch({
    '/api/v1/meta/options': { body: options },
    '/api/v1/movies': () => ({ body: list }),
    '/api/v1/movies/new-and-upcoming': () => (live === 'error' ? { status: 500, body: { detail: 'boom' } }
      : pending ? new Promise(() => {}) : { body: live }),
  })
}
const many = (n: number): LiveMovie[] => Array.from({ length: n }, (_, i) => ({ ...TRAIN, tmdb_id: 7000 + i, title: `Film ${i}`, movie_id: null }))
const row = (name: string) => screen.findByRole('region', { name })

describe('words', () => {
  test('badges, footers and dates', () => {
    expect(statusBadge({ status: 'out_today', release_date: '2026-10-30' })).toBe('Out today')
    expect(statusBadge({ status: 'new', release_date: '2026-10-20' })).toBe('New')
    expect(statusBadge({ status: 'upcoming', release_date: '2026-11-14' })).toBe('Nov 14')
    expect(footerLabel({ status: 'new', release_date: '2026-10-20', vote_average: 7.4 })).toBe('7.4')
    expect(footerLabel({ status: 'new', release_date: '2026-10-20', vote_average: null })).toBe('Not rated yet')
    expect(footerLabel({ status: 'upcoming', release_date: '2026-11-14', vote_average: null })).toBe('Coming Nov 14')
    expect(shortDate('2026-01-01')).toBe('Jan 1')
    expect(releaseLine({ status: 'upcoming', release_date: '2026-11-14' })).toBe('In cinemas Nov 14, 2026')
    expect(releaseLine({ status: 'new', release_date: '2026-10-24' })).toBe('Released Oct 24, 2026')
  })

  test('how long ago', () => {
    const now = Date.parse('2026-10-30T12:00:00Z')
    expect(updatedAgo('2026-10-30T10:00:00Z', now)).toBe('Updated 2 hours ago')
    expect(updatedAgo('2026-10-30T11:59:30Z', now)).toBe('Updated just now')
    expect(updatedAgo('2026-10-30T11:01:00Z', now)).toBe('Updated 59 minutes ago')
    expect(updatedAgo(null, now)).toBe('')
  })

  test('the form started from a live film keeps its genres and release month', () => {
    const form = liveToForm({ genres: ['Science Fiction', 'Nonsense'], release_date: '2026-11-14' }, options, new Date('2026-10-30'))
    expect(form.genres).toEqual(['Science Fiction'])
    expect(form.release_month).toBe(11)
    expect(form.release_year).toBe(2026)
  })
})

describe('the rows', () => {
  test('both show on the default browse view and on /movies, and not under a filter or a search', async () => {
    serve()
    renderApp('/browse')
    await row('New Arrivals')
    expect(screen.getByRole('region', { name: 'Coming soon' })).toBeInTheDocument()
    cleanup()
    renderApp('/movies')
    await row('New Arrivals')
    cleanup()
    renderApp('/browse?genre=Drama')
    await screen.findAllByRole('link', { name: /poster/i })
    expect(screen.queryByRole('region', { name: 'New Arrivals' })).toBeNull()
    cleanup()
    renderApp('/browse?q=dune')
    await screen.findAllByRole('link', { name: /poster/i })
    expect(screen.queryByRole('region', { name: 'New Arrivals' })).toBeNull()
  })

  test('a row has at most 20 cards and a See all link to its tab', async () => {
    serve({ live: { ...LIVE, new: many(35) } })
    renderApp('/browse')
    const region = await row('New Arrivals')
    expect(within(region).getAllByTestId('live-card')).toHaveLength(20)
    expect(within(region).getByRole('link', { name: /see all/i })).toHaveAttribute('href', '/new-and-upcoming?tab=out-now')
    expect(within(screen.getByRole('region', { name: 'Coming soon' })).getByRole('link', { name: /see all/i }))
      .toHaveAttribute('href', '/new-and-upcoming?tab=coming-soon')
  })

  test('an error hides the rows and the grid still shows', async () => {
    serve({ live: 'error' })
    renderApp('/browse')
    expect(await screen.findAllByRole('link', { name: /poster/i })).not.toHaveLength(0)
    await waitFor(() => expect(screen.queryByTestId('live-row-skeleton')).toBeNull())
    expect(screen.queryByRole('region', { name: 'New Arrivals' })).toBeNull()
  })

  test('an empty list hides only its own row', async () => {
    serve({ live: { ...LIVE, upcoming: [] } })
    renderApp('/browse')
    await row('New Arrivals')
    expect(screen.queryByRole('region', { name: 'Coming soon' })).toBeNull()
  })

  test('a skeleton holds the space while the live request is pending', async () => {
    serve({ pending: true })
    renderApp('/browse')
    expect(await screen.findByTestId('live-row-skeleton')).toBeInTheDocument()
  })
})

describe('the card and the quick view', () => {
  test('a film in our database links to its page, any other is a button', async () => {
    serve()
    renderApp('/browse')
    const region = await row('New Arrivals')
    expect(within(region).getByRole('link', { name: /Already Here/ })).toHaveAttribute('href', `/movies/${HERE.movie_id}`)
    expect(within(region).getByRole('button', { name: /Night Train/ })).toBeInTheDocument()
  })

  test('the button opens a modal; Esc closes it and the focus returns to the card', async () => {
    serve()
    const { router } = renderApp('/browse')
    const card = await screen.findByRole('button', { name: /Night Train/ })
    await userEvent.click(card)
    const dialog = await screen.findByRole('dialog', { name: TRAIN.title })
    expect(router.state.location.search).toBe(`?film=${TRAIN.tmdb_id}`)
    expect(within(dialog).getByText('Released Oct 30, 2026')).toBeInTheDocument()
    expect(within(dialog).getByText('Not rated yet')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'View on TMDB' })).toHaveAttribute('rel', 'noopener noreferrer')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(router.state.location.search).toBe('')
    expect(card).toHaveFocus()
  })

  test('"Predict a film like this" opens the form with the film\'s genres and month', async () => {
    serve()
    const { router } = renderApp(`/browse?film=${DUNE.tmdb_id}`)
    const dialog = await screen.findByRole('dialog', { name: DUNE.title })
    expect(within(dialog).getByText('In cinemas Nov 14, 2026')).toBeInTheDocument()
    const button = within(dialog).getByRole('button', { name: 'Predict a film like this' })
    await waitFor(() => expect(button).toBeEnabled())
    await userEvent.click(button)
    await waitFor(() => expect(router.state.location.pathname).toBe('/predict'))
    const search = new URLSearchParams(router.state.location.search)
    expect(search.get(LIKE_PARAM)).toBe(DUNE.title)
    const form = decodeForm(search.get(URL_PARAM))!
    expect(form.genres).toEqual(['Science Fiction', 'Adventure'])
    expect(form.release_month).toBe(11)
  })

  test('?film= with an id that is not in the lists is removed', async () => {
    serve()
    const { router } = renderApp('/browse?film=999')
    await waitFor(() => expect(router.state.location.search).toBe(''))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  test('?film= while the live request fails is removed too', async () => {
    serve({ live: 'error' })
    const { router } = renderApp('/browse?film=9001')
    await waitFor(() => expect(router.state.location.search).toBe(''))
  })
})

describe('/new-and-upcoming', () => {
  test('the tab is in the URL and an unknown tab is corrected', async () => {
    serve()
    const { router } = renderApp('/new-and-upcoming?tab=nope')
    await screen.findByRole('tab', { name: 'Out now', selected: true })
    expect(router.state.location.search).toBe('?tab=out-now')
    await userEvent.click(screen.getByRole('tab', { name: 'Coming soon' }))
    expect(router.state.location.search).toBe('?tab=coming-soon')
    expect(await screen.findByRole('button', { name: /Dune Four/ })).toBeInTheDocument()
  })

  test('24 a page, a pager, and when it was updated', async () => {
    serve({ live: { ...LIVE, new: many(30), fetched_at: new Date(Date.now() - 2 * 3600_000).toISOString() } })
    renderApp('/new-and-upcoming?tab=out-now')
    expect(await screen.findAllByTestId('live-card')).toHaveLength(24)
    expect(screen.getByText('Updated 2 hours ago')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Page 2' }))
    await waitFor(() => expect(screen.getAllByTestId('live-card')).toHaveLength(6))
  })

  test('an error says so and offers Retry and a way back', async () => {
    const { calls } = serve({ live: 'error' })
    renderApp('/new-and-upcoming?tab=out-now')
    expect(await screen.findByText("We can't load new releases right now.")).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to browse' })).toHaveAttribute('href', '/browse')
    const before = calls.filter(c => c.url.pathname.endsWith('new-and-upcoming')).length
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(calls.filter(c => c.url.pathname.endsWith('new-and-upcoming')).length).toBe(before + 1))
  })

  test('the navigation has a link to it', async () => {
    serve()
    renderApp('/about')
    expect(await screen.findAllByRole('link', { name: 'New' })).not.toHaveLength(0)
  })
})

describe('search', () => {
  test('the header dropdown shows live matches after the database rows, under a label', async () => {
    serve({ list: { ...FILMS, live_matches: [DUNE] } })
    renderApp('/about')
    await userEvent.type(await screen.findByRole('combobox', { name: /search/i }), 'dune')
    expect(await screen.findByText('New & upcoming')).toBeInTheDocument()
    const option = screen.getByRole('option', { name: /Dune Four/ })
    expect(within(option).getByText('Nov 14')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /See all/ })).toBeInTheDocument()
  })

  test('picking a live result opens its quick view', async () => {
    serve({ list: { ...FILMS, live_matches: [DUNE] } })
    const { router } = renderApp('/about')
    await userEvent.type(await screen.findByRole('combobox', { name: /search/i }), 'dune')
    await userEvent.click(await screen.findByRole('option', { name: /Dune Four/ }))
    expect(router.state.location.pathname).toBe('/about')
    expect(await screen.findByRole('dialog', { name: DUNE.title })).toBeInTheDocument()
  })

  test('browse shows a strip of live matches above the results', async () => {
    serve({ list: { ...FILMS, live_matches: [DUNE] } })
    renderApp('/browse?q=dune')
    const strip = await screen.findByTestId('live-matches')
    expect(within(strip).getByRole('button', { name: /Dune Four/ })).toBeInTheDocument()
  })

  test('with no database result the live matches replace "No movies match"', async () => {
    serve({ list: { items: [], total: 0, page: 1, page_size: 24, pages: 0, live_matches: [DUNE] } })
    renderApp('/browse?q=dune four')
    expect(await screen.findByRole('button', { name: /Dune Four/ })).toBeInTheDocument()
    expect(screen.queryByText(/No movies match/)).toBeNull()
  })
})
