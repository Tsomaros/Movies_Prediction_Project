// /people?q= (V1.1): the heading and cards, the role chips, the URL state, the empty and short-query states and a
// page past the end. people_search_nolan.json is a real API answer (75 people: 68 actors, 3 directors, 10 writers).
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'

import { mockFetch } from '@/test/fetch'
import nolan from '@/test/people_search_nolan.json'
import { renderApp } from '@/test/render'

const EMPTY = { ...nolan, total: 0, role_counts: { all: 0, actor: 0, director: 0, writer: 0 }, results: [] }

function api(page: unknown = nolan, moviesTotal = 0) {
  return mockFetch({
    '/api/v1/people/search': { body: page },
    '/api/v1/movies': { body: { items: [], total: moviesTotal, page: 1, page_size: 1, pages: moviesTotal } },
  })
}

test('the heading, the total and one card per person, each a link to their page', async () => {
  const fetch = api()
  renderApp('/people?q=nolan')
  expect(await screen.findByRole('heading', { level: 1, name: 'People matching ‘nolan’' })).toBeInTheDocument()
  expect(await screen.findByText('75 people')).toBeInTheDocument()
  expect(screen.getAllByTestId('person-card')).toHaveLength(24)
  expect(screen.getByRole('link', { name: /Christopher Nolan/ })).toHaveAttribute('href', '/people/525')
  expect(screen.getByText('Director, Writer, Actor')).toBeInTheDocument()
  expect(screen.getByRole('navigation', { name: 'Pages' })).toBeInTheDocument()
  await waitFor(() => expect(document.title).toBe('People: nolan · Movie Prediction'))
  expect(fetch.calls.find(c => c.url.pathname === '/api/v1/people/search')!.url.search).toBe('?q=nolan&role=all&page=1&page_size=24')
})

test('role chips show their counts, an empty one is disabled, and a chip goes to page 1 of that role', async () => {
  const { router } = (api({ ...nolan, role_counts: { ...nolan.role_counts, writer: 0 } }), renderApp('/people?q=nolan&page=2'))
  expect(await screen.findByRole('button', { name: 'Writers 0' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'All 75' })).toHaveAttribute('aria-pressed', 'true')
  await userEvent.click(screen.getByRole('link', { name: 'Directors 3' }))
  await waitFor(() => expect(router.state.location.search).toBe('?q=nolan&role=director'))
})

test('an unknown role is All, and the address is corrected in place', async () => {
  const fetch = api()
  const { router } = renderApp('/people?q=nolan&role=producer')
  await screen.findByText('75 people')
  await waitFor(() => expect(router.state.location.search).toBe('?q=nolan'))
  expect(fetch.calls.every(c => c.url.pathname !== '/api/v1/people/search' || c.url.searchParams.get('role') === 'all')).toBe(true)
})

test('nobody found points to the matching films', async () => {
  api(EMPTY, 1)
  renderApp('/people?q=inception')
  expect(await screen.findByText('No people match ‘inception’.')).toBeInTheDocument()
  expect(await screen.findByRole('link', { name: /1 movie found/ })).toHaveAttribute('href', '/browse?q=inception')
})

test('too short a name asks for one and puts the focus in the header search', async () => {
  const fetch = api()
  renderApp('/people?q=a')
  expect(await screen.findByText('Type a name in the search bar above.')).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('combobox', { name: /search/i })).toHaveFocus())
  expect(fetch.calls.some(c => c.url.pathname === '/api/v1/people/search')).toBe(false)
})

test('a page past the end says so and links back to page 1', async () => {
  api({ ...nolan, page: 9, results: [] })
  renderApp('/people?q=nolan&page=9')
  expect(await screen.findByText("This page doesn't exist")).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Back to page 1' })).toHaveAttribute('href', '/people?q=nolan')
})
