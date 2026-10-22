import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, test, vi } from 'vitest'

import { THEME_KEY } from '@/app/theme'
import { RouteError } from '@/pages/NotFound'
import { mockSystemTheme } from '@/test/setup'
import { renderApp } from '@/test/render'

describe('routes', () => {
  test.each([
    ['/', 'How might your film do?'],
    ['/predict', 'Plan a film'],
    ['/predict/result', 'Your prediction'],
    ['/movies', 'Browse films'],
    ['/movies/603', 'Film'],
    ['/no/such/page', 'Page not found'],
  ])('%s shows "%s"', async (path, heading) => {
    renderApp(path)
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  test('every page has the header, the navigation and the TMDB notice', () => {
    renderApp('/movies')
    expect(screen.getByRole('link', { name: /Movie Prediction/ })).toHaveAttribute('href', '/')
    expect(screen.getAllByRole('navigation', { name: 'Main' }).length).toBeGreaterThan(0)
    expect(screen.getByTestId('tmdb-attribution')).toHaveTextContent('not endorsed or certified by TMDB')
  })

  test('the navigation moves between pages and marks the current one', async () => {
    const { router } = renderApp('/')
    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0]
    await userEvent.click(within(nav).getByRole('link', { name: 'Plan a film' }))
    expect(router.state.location.pathname).toBe('/predict')
    expect(within(nav).getByRole('link', { name: 'Plan a film' })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByRole('heading', { level: 1, name: 'Plan a film' })).toBeInTheDocument()
  })
})

describe('theme', () => {
  test('starts from the system preference', async () => {
    mockSystemTheme(true)
    renderApp('/')
    await waitFor(() => expect(document.documentElement).toHaveClass('dark'))
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument()
  })

  test('the toggle switches the theme and remembers the choice', async () => {
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Switch to dark theme' }))
    await waitFor(() => expect(document.documentElement).toHaveClass('dark'))
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    await waitFor(() => expect(document.documentElement).not.toHaveClass('dark'))
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
  })

  test('a saved choice wins over the system preference', async () => {
    mockSystemTheme(true)
    localStorage.setItem(THEME_KEY, 'light')
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument()
    expect(document.documentElement).not.toHaveClass('dark')
  })
})

describe('a page that crashes', () => {
  test('shows "Something went wrong" with a reload button, not a blank screen', async () => {
    const Boom = () => { throw new Error('boom') }
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs the thrown error
    const router = createMemoryRouter([{ path: '/', element: <Boom />, errorElement: <RouteError /> }])
    render(<RouterProvider router={router} />)
    expect(await screen.findByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })
})
