// A page that crashes shows "Something went wrong" inside the Layout: the header, navigation and footer keep
// working, so the visitor can go elsewhere without reloading. (Its own file: the About page is mocked to throw.)
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { mockFetch } from '@/test/fetch'
import { renderApp } from '@/test/render'

vi.mock('@/pages/About', () => ({ default: () => { throw new Error('boom') } }))

afterEach(() => vi.unstubAllGlobals())

test('a crash inside a page keeps the navigation working', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs the thrown error
  mockFetch({})
  const { router } = renderApp('/about')
  expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
  expect(screen.getByTestId('tmdb-attribution')).toBeInTheDocument()
  await userEvent.click(screen.getAllByRole('link', { name: 'Browse films' })[0])
  await waitFor(() => expect(router.state.location.pathname).toBe('/movies')) // the page loads on demand
  expect(await screen.findByRole('heading', { level: 1, name: 'Browse films' })).toBeInTheDocument()
})
