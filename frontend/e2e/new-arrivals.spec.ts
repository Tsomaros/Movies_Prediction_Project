// New arrivals (V1.2) in a real browser against the running app: the first row of /movies opens an ordinary film
// page, and a film planned from there is in My movies. Needs at least one released new film merged in (the app
// needs TMDB_READ_TOKEN: make docker-run takes it from .env) and the demo account (make userdb). It cleans up
// after itself, like demo.spec.ts, so it can run again on the shared account.
import { expect, test } from '@playwright/test'

test('a new arrival opens its film page, can be planned, and is in My movies', async ({ page }) => {
  await page.goto('/movies')
  const row = page.getByTestId('row-new')
  await expect(row.getByRole('heading', { name: 'New arrivals' })).toBeVisible()
  await expect(row.getByRole('radio', { name: 'Just released' })).toBeChecked()
  const first = row.getByRole('list').getByRole('link').first()
  await expect(first).toBeVisible({ timeout: 15_000 })
  await first.click()
  await expect(page).toHaveURL(/\/movies\/\d+$/)
  const filmUrl = page.url()
  const title = (await page.getByRole('heading', { level: 1 }).textContent())?.replace(/\s*\(\d{4}\)\s*$/, '').trim() ?? ''
  expect(title.length).toBeGreaterThan(0)
  await expect(page.getByTestId('release-label')).toHaveText('New release')

  // A logged-out click opens the login dialog; the demo login completes it
  const lists = page.getByRole('radiogroup', { name: 'Your lists' })
  await lists.getByRole('radio', { name: 'Plan to watch' }).click()
  await page.getByRole('dialog').getByRole('button', { name: /Try the demo account/ }).click()
  await expect(page.getByRole('button', { name: 'Account menu for demo' })).toBeVisible()
  await expect(lists.getByRole('radio', { name: 'Plan to watch' })).toHaveAttribute('aria-checked', 'true')

  await page.goto('/my-movies')
  await page.getByRole('tab', { name: /^Plan to watch/ }).click()
  await expect(page.getByRole('list', { name: 'Films' }).getByRole('listitem').filter({ hasText: title })).toBeVisible()

  await page.goto(filmUrl) // clean up: the film leaves the list
  await lists.getByRole('radio', { name: 'Not in a list' }).click()
  await expect(lists.getByRole('radio', { name: 'Not in a list' })).toHaveAttribute('aria-checked', 'true')
})

test('the switch shows what is coming, and "See all" opens Browse with the same window', async ({ page }) => {
  await page.goto('/movies')
  const row = page.getByTestId('row-new')
  await row.getByRole('radio', { name: 'Coming soon' }).click()
  await expect(row.getByRole('link', { name: /see all/i })).toHaveAttribute('href', '/browse?when=upcoming&sort=soonest')
  await row.getByRole('link', { name: /see all/i }).click()
  await expect(page.getByRole('button', { name: /remove filter coming soon/i })).toBeVisible()
})
