import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { mockFetch } from '@/test/fetch'
import { mockSystemTheme } from '@/test/setup'
import { renderApp } from '@/test/render'

afterEach(() => { vi.unstubAllGlobals(); mockSystemTheme(false) })

function mockReducedMotion() {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('reduced-motion'), media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => false,
  }))
}

describe('the start page', () => {
  test('two panels link to movies and series, over their collages', async () => {
    renderApp('/')
    const movies = await screen.findByRole('link', { name: /^Movies Browse 80,000 films/ })
    const series = screen.getByRole('link', { name: /^Series Coming soon/ })
    expect(movies).toHaveAttribute('href', '/movies')
    expect(series).toHaveAttribute('href', '/series')
    expect(movies.querySelector('img')).toHaveAttribute('src', '/collages/movies.webp')
    expect(series.querySelector('img')).toHaveAttribute('src', '/collages/series.webp')
    expect(screen.getByRole('heading', { level: 2, name: 'Movies' })).toBeInTheDocument()
  })

  test('the collages pan, unless the visitor prefers reduced motion', async () => {
    const { unmount } = renderApp('/')
    for (const name of ['movies', 'series']) {
      const panel = await screen.findByTestId(`panel-${name}`)
      expect(panel).toHaveAttribute('data-pan', 'on')
      expect(panel.querySelector('img')).toHaveClass('animate-pan')
    }
    unmount()
    mockReducedMotion()
    renderApp('/')
    for (const name of ['movies', 'series']) {
      const panel = await screen.findByTestId(`panel-${name}`)
      expect(panel).toHaveAttribute('data-pan', 'off')
      expect(panel.querySelector('img')).not.toHaveClass('animate-pan')
    }
  })

  test("no header or footer; Predict, About, the theme and TMDB's notice sit under the cards", async () => {
    mockFetch({})
    const { router } = renderApp('/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Movie Prediction' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    expect(screen.queryByRole('contentinfo')).not.toBeInTheDocument()
    expect(screen.getByTestId('tmdb-attribution')).toHaveTextContent('not endorsed or certified by TMDB')
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('href', '/about')
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Predict a film' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/predict')) // the page loads on demand
    expect((await screen.findAllByRole('navigation', { name: 'Main' })).length).toBeGreaterThan(0) // other pages keep the header
  })
})

describe('the series page', () => {
  test('says coming soon and sends the visitor to the films', async () => {
    mockFetch({})
    const { router } = renderApp('/series')
    expect(await screen.findByRole('heading', { level: 1, name: 'Series: coming soon' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Browse movies' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/movies'))
  })
})
