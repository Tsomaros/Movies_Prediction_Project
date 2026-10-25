import { fireEvent, render, screen, within } from '@testing-library/react'
import { cloneElement, isValidElement, type ReactNode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, test, vi } from 'vitest'

import type { CareerResponse, CareerView } from '@/api/client'
import { CareerChart } from '@/career/CareerChart'
import { CareerTable } from '@/career/CareerTable'
import { money } from '@/result/format'
import fewJson from '@/test/career_few.json'
import hanksJson from '@/test/career_hanks.json'
import nolanJson from '@/test/career_nolan.json'

// jsdom has no layout, so the container gives the chart a fixed size (the usual Recharts test setup)
vi.mock('recharts', async importOriginal => {
  const recharts = await importOriginal<typeof import('recharts')>()
  return {
    ...recharts,
    ResponsiveContainer: ({ children }: { children: ReactNode }) =>
      isValidElement(children) ? cloneElement(children as React.ReactElement<{ width: number; height: number }>, { width: 800, height: 260 }) : null,
  }
})

// Real answers: Tom Hanks as an actor (77 of 85 films rated), Christopher Nolan as a director and Hanna Hall
// (3 rated films: no forecast)
const HANKS = hanksJson as CareerResponse
const NOLAN = nolanJson as CareerResponse
const FEW = fewJson as CareerResponse

function chart(data: CareerResponse, view: CareerView = 'score', open = vi.fn()) {
  render(<CareerChart data={data} view={view} onOpenMovie={open} />)
  return open
}
const scored = (data: CareerResponse) => data.films.filter(f => f.score !== null)

describe('the career chart', () => {
  test('dot styles follow lead, supporting, crew and low votes; the best film and the band are marked', () => {
    chart(HANKS)
    const films = scored(HANKS)
    expect(screen.getAllByTestId('dot-lead')).toHaveLength(films.filter(f => f.rated && f.lead).length)
    expect(screen.getAllByTestId('dot-support')).toHaveLength(films.filter(f => f.rated && f.lead === false).length)
    expect(screen.getAllByTestId('dot-faint')).toHaveLength(films.filter(f => !f.rated).length)
    expect(screen.queryByTestId('dot-crew')).toBeNull()
    expect(within(screen.getByTestId('best-marker')).getByText('Best: 8.5')).toBeInTheDocument()
    expect(screen.getByTestId('forecast-band')).toBeInTheDocument()
    expect(screen.getByText('Next film')).toBeInTheDocument()
  })

  test('crew films are filled dots', () => {
    chart(NOLAN)
    expect(screen.getAllByTestId('dot-crew')).toHaveLength(scored(NOLAN).filter(f => f.rated).length)
    expect(screen.queryByTestId('dot-lead')).toBeNull()
  })

  test('no band without a forecast', () => {
    chart(FEW)
    expect(FEW.metrics.score.forecast.status).toBe('not_enough_films')
    expect(screen.queryByTestId('forecast-band')).toBeNull()
    expect(screen.getByTestId('best-marker')).toBeInTheDocument()
  })

  test('revenue: dots only for films with a box office (none faint), the band, a money best label and log ticks', () => {
    chart(HANKS, 'revenue')
    const known = HANKS.films.filter(f => f.revenue !== null)
    expect(known.length).toBeLessThan(HANKS.films.length)
    expect(screen.getAllByTestId(/^dot-/)).toHaveLength(known.length)
    expect(screen.getAllByTestId('dot-lead')).toHaveLength(known.filter(f => f.lead).length)
    expect(screen.getAllByTestId('dot-support')).toHaveLength(known.filter(f => f.lead === false).length)
    expect(screen.queryByTestId('dot-faint')).toBeNull()
    expect(HANKS.metrics.revenue.best_film!.title).toBe('Toy Story 3')
    expect(within(screen.getByTestId('best-marker')).getByText('Best: $1.6B')).toBeInTheDocument()
    expect(screen.getByTestId('forecast-band')).toBeInTheDocument()
    for (const tick of ['$10M', '$100M', '$1B']) expect(screen.getByText(tick)).toBeInTheDocument()
  })

  test('revenue: crew films are filled, and the tooltip shows the box office', () => {
    chart(NOLAN, 'revenue')
    expect(screen.getAllByTestId('dot-crew')).toHaveLength(NOLAN.films.filter(f => f.revenue !== null).length)
    const best = screen.getByTestId('best-marker').parentElement!
    fireEvent.pointerEnter(best, { pointerType: 'mouse' })
    const film = NOLAN.films.find(f => f.movie_id === NOLAN.metrics.revenue.best_film!.movie_id)!
    expect(screen.getByRole('tooltip')).toHaveTextContent(`2012 · ${money(film.revenue!)} box office`)
  })

  test('a view with no values says so instead of an empty chart', () => {
    chart({ ...FEW, films: FEW.films.map(f => ({ ...f, revenue: null })) }, 'revenue')
    expect(screen.getByText('No films with a known box office to chart')).toBeInTheDocument()
    expect(screen.queryByTestId(/^dot-/)).toBeNull()
  })

  test('mouse: hover shows the film, a click opens it', () => {
    const open = chart(HANKS)
    const best = screen.getByTestId('best-marker').parentElement!
    fireEvent.pointerEnter(best, { pointerType: 'mouse' })
    const tip = screen.getByRole('tooltip')
    expect(tip).toHaveTextContent('The Green Mile')
    expect(tip).toHaveTextContent('1999 · 8.5')
    expect(tip).toHaveTextContent('as Paul Edgecomb')
    expect(tip).toHaveTextContent('Lead role')
    fireEvent.pointerDown(best, { pointerType: 'mouse' })
    fireEvent.click(best)
    expect(open).toHaveBeenCalledWith(HANKS.metrics.score.best_film!.movie_id)
  })

  test('touch: the first tap shows the film, a second tap on the same dot opens it', () => {
    const open = chart(HANKS)
    const [first, second] = screen.getAllByTestId('dot-lead')
    const tap = (el: HTMLElement) => { fireEvent.pointerDown(el, { pointerType: 'touch' }); fireEvent.click(el) }
    tap(first)
    expect(open).not.toHaveBeenCalled()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    tap(second) // another dot: its details, still not opened
    expect(open).not.toHaveBeenCalled()
    tap(second)
    const leads = scored(HANKS).filter(f => f.rated && f.lead)
    expect(open).toHaveBeenCalledWith(leads[1].movie_id)
  })
})

describe('the career table', () => {
  test('lists every dated film with a link, score, box office, votes and role', () => {
    const router = createMemoryRouter([{ path: '/', element: <CareerTable films={HANKS.films} /> }])
    render(<RouterProvider router={router} />)
    const table = screen.getByRole('table', { name: 'Career films' })
    expect(within(table).getAllByRole('row')).toHaveLength(HANKS.films.length + 1)
    const green = within(table).getByRole('link', { name: 'The Green Mile' })
    expect(green).toHaveAttribute('href', `/movies/${HANKS.metrics.score.best_film!.movie_id}`)
    expect(green.closest('tr')).toHaveTextContent(/1999The Green Mile8\.5\$[\d.]+[MB][\d,]+as Paul Edgecomb · lead/)
    const none = HANKS.films.find(f => f.revenue === null)!
    expect(within(table).getByRole('link', { name: none.title }).closest('tr')).toHaveTextContent(/—/)
  })
})
