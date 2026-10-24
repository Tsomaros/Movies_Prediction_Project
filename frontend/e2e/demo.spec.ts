// The demo account's whole path in a real browser (Day 14; Day 15 reruns it against the live site):
// demo login -> mark a film watched with a rating -> add a note -> see both in My movies; then a "Surprise me" spin.
// It cleans up after itself (the film leaves the lists, the note is deleted), so it can run again on the
// shared account; the nightly reset restores the starting set anyway.
import { expect, test } from '@playwright/test'

const FILM = { id: 1726, title: 'Iron Man' } // not in the demo's starting set
const NOTE = `Playwright note ${Date.now()}`

test('demo login, a rating and a note, then both in My movies', async ({ page }) => {
  await page.goto(`/movies/${FILM.id}`)
  await expect(page.getByRole('heading', { level: 1, name: new RegExp(FILM.title) })).toBeVisible()

  // A logged-out click opens the login dialog; the demo login completes it
  const lists = page.getByRole('radiogroup', { name: 'Your lists' })
  await lists.getByRole('radio', { name: 'Watched' }).click()
  await page.getByRole('dialog').getByRole('button', { name: /Try the demo account/ }).click()
  await expect(page.getByRole('button', { name: 'Account menu for demo' })).toBeVisible()
  await expect(lists.getByRole('radio', { name: 'Watched' })).toHaveAttribute('aria-checked', 'true')

  // 8 out of 10 by keyboard, saved once the keys stop
  await page.getByRole('radio', { name: '1 out of 10' }).focus()
  await page.keyboard.press('End')
  for (let i = 0; i < 2; i++) await page.keyboard.press('ArrowLeft')
  await expect(page.getByTestId('your-rating')).toHaveText('8/10')
  await expect(page.getByTestId('film-your-rating')).toContainText('You: 8/10')

  // A note, saved with Ctrl+Enter
  await page.getByRole('textbox', { name: 'New note' }).fill(NOTE)
  await page.keyboard.press('Control+Enter')
  await expect(page.getByRole('list', { name: 'Notes, newest first' }).getByText(NOTE)).toBeVisible()

  // Both in My movies, after a reload (so they came from the server)
  await page.goto('/my-movies?sort=title')
  const card = page.getByRole('list', { name: 'Films' }).getByRole('listitem').filter({ hasText: FILM.title })
  await expect(card.getByText('Watched, rated 8/10')).toBeAttached()
  await page.getByRole('tab', { name: /^Notes/ }).click()
  await expect(page.getByText(NOTE)).toBeVisible()

  // Clean up: delete the note, take the film out of the lists
  await page.goto(`/movies/${FILM.id}`)
  const note = page.getByRole('list', { name: 'Notes, newest first' }).getByRole('listitem').filter({ hasText: NOTE })
  await note.getByRole('button', { name: 'Delete note' }).click()
  await expect(note).toHaveCount(0)
  await lists.getByRole('radio', { name: 'Not in a list' }).click()
  await expect(lists.getByRole('radio', { name: 'Not in a list' })).toHaveAttribute('aria-checked', 'true')
  await page.reload()
  await expect(page.getByRole('radiogroup', { name: 'Your lists' }).getByRole('radio', { name: 'Not in a list' }))
    .toHaveAttribute('aria-checked', 'true')
})

test('Surprise me: a spin, a second spin with a different film, then its page', async ({ page }) => {
  await page.goto('/movies')
  await page.getByRole('button', { name: 'Surprise me' }).click()
  const dialog = page.getByRole('dialog', { name: 'Surprise me' })
  await dialog.getByRole('radio', { name: "Anything I haven't seen" }).click()
  await dialog.getByRole('button', { name: /^Spin/ }).click()
  const title = dialog.getByRole('heading', { level: 3 })
  await expect(title).toBeVisible({ timeout: 10_000 })
  const first = await title.textContent()
  await dialog.getByRole('button', { name: 'Spin again' }).click()
  await expect(title).not.toHaveText(first!, { timeout: 10_000 })
  const second = await title.textContent()
  await dialog.getByRole('link', { name: 'Open details' }).click()
  await expect(page).toHaveURL(/\/movies\/\d+$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText(second!)
})
