// New Arrivals and Coming soon (V1.2) in a real browser, with the live endpoint answered by the test (TMDB is not
// asked): a card opens the quick view, "Predict a film like this" opens a form that already has its genres, and an
// upcoming film that is not in our database can be found from the header search.
import { expect, test, type Page } from '@playwright/test'

const film = (over: Record<string, unknown>) => ({
  tmdb_id: 9101, movie_id: null, title: 'Dune Four', original_title: 'Dune Four', release_date: '2026-11-14', year: 2026,
  poster: { small: 'https://image.tmdb.org/t/p/w342/x.jpg', large: 'https://image.tmdb.org/t/p/w780/x.jpg' },
  overview: 'A story told in one sentence.', genres: ['Science Fiction', 'Adventure'], vote_average: null, vote_count: 0,
  popularity: 90, status: 'upcoming', ...over,
})
const LIVE = {
  fetched_at: new Date().toISOString(), stale: false,
  new: [film({ tmdb_id: 9001, title: 'Night Train', release_date: '2026-10-30', status: 'out_today', genres: ['Thriller'] })],
  upcoming: [film({})],
}

async function mockLive(page: Page) {
  await page.route('**/api/v1/movies/new-and-upcoming', route => route.fulfill({ json: LIVE }))
  await page.route('**/api/v1/movies?*q=dune*', async route => {
    const real = await route.fetch()
    await route.fulfill({ response: real, json: { ...(await real.json()), live_matches: LIVE.upcoming } })
  })
}

test('a new arrival opens the quick view, and "Predict a film like this" starts the form', async ({ page }) => {
  await mockLive(page)
  await page.goto('/browse')
  await page.getByRole('region', { name: 'New Arrivals' }).getByRole('button', { name: /Night Train/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Night Train' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Predict a film like this' }).click()
  await expect(page).toHaveURL(/\/predict\?.*f=/)
  await expect(page.getByRole('button', { name: /Thriller/ }).first()).toBeVisible()
})

test('an upcoming film is found from the header search', async ({ page }) => {
  await mockLive(page)
  await page.goto('/')
  await page.getByRole('combobox', { name: /search/i }).fill('dune four')
  await page.getByRole('option', { name: /Dune Four/ }).click()
  await expect(page.getByRole('dialog', { name: 'Dune Four' })).toBeVisible()
})
