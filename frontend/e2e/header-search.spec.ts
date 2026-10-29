// The header search (V1.1) in a real browser: a movies search that finds no films points to the people, the
// people results open an actor's page and Back returns to them; on a phone the overlay opens a film and closes.
import { expect, test } from '@playwright/test'

test('a movies search for a person points to People; the actor opens and Back restores the results', async ({ page }) => {
  await page.goto('/about')
  const box = page.getByRole('combobox', { name: 'Search movies' })
  await box.fill('tom hanks')
  await page.getByRole('link', { name: /(person|people) found/ }).click()
  await expect(page).toHaveURL(/\/people\?q=tom(\+|%20)hanks$/)
  await expect(page.getByRole('heading', { level: 1, name: 'People matching ‘tom hanks’' })).toBeVisible()
  await page.getByRole('list', { name: 'People' }).getByRole('link', { name: /Tom Hanks/ }).click()
  await expect(page).toHaveURL(/\/people\/31$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Tom Hanks' })).toBeVisible()
  await page.goBack()
  await expect(page.getByRole('heading', { level: 1, name: /People matching/ })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Search people' })).toHaveValue('tom hanks')
})

test('Enter opens the movie results; "/" focuses the box from anywhere', async ({ page }) => {
  await page.goto('/browse')
  await expect(page.getByRole('list', { name: 'Films' })).toBeVisible()
  await page.keyboard.press('/')
  const box = page.getByRole('combobox', { name: 'Search movies' })
  await expect(box).toBeFocused()
  await box.fill('inception')
  await expect(page.getByRole('option', { name: /Inception/ }).first()).toBeVisible()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/browse\?q=inception$/)
  await expect(page.getByText('Results for ‘inception’')).toBeVisible()
})

test('on a phone the icon opens the overlay; a result opens and the overlay is gone', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/about')
  await page.getByRole('button', { name: 'Search' }).click()
  const dialog = page.getByRole('dialog', { name: 'Search' })
  await dialog.getByRole('combobox').fill('incep')
  await dialog.getByRole('option').first().click()
  await expect(dialog).toBeHidden()
  await expect(page).toHaveURL(/\/movies\/\d+$/)
})
