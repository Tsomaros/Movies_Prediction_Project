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
    const movies = await screen.findByRole('link', { name: /^Movies Browse 79,000 films/ })
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

  test('the header reaches Predict from the start page', async () => {
    mockFetch({})
    const { router } = renderApp('/')
    const nav = screen.getAllByRole('navigation', { name: 'Main' })[0]
    expect([...nav.querySelectorAll('a')].map(a => a.textContent)).toEqual(['Movies', 'Browse', 'Predict', 'About'])
    await userEvent.click(screen.getAllByRole('link', { name: 'Predict' })[0])
    await waitFor(() => expect(router.state.location.pathname).toBe('/predict')) // the page loads on demand
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
