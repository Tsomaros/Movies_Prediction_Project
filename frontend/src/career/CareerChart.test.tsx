import { fireEvent, render, screen, within } from '@testing-library/react'
import { cloneElement, isValidElement, type ReactNode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, test, vi } from 'vitest'

import type { CareerResponse } from '@/api/client'
import { CareerChart } from '@/career/CareerChart'
import { CareerTable } from '@/career/CareerTable'
import { chartSummary } from '@/career/explain'
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

function chart(data: CareerResponse, open = vi.fn()) {
  render(<CareerChart data={data} onOpenMovie={open} />)
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
    expect(FEW.forecast.status).toBe('not_enough_films')
    expect(screen.queryByTestId('forecast-band')).toBeNull()
    expect(screen.getByTestId('best-marker')).toBeInTheDocument()
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
    expect(open).toHaveBeenCalledWith(HANKS.best_film!.movie_id)
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

  test('screen readers get one summary sentence', () => {
    expect(chartSummary(HANKS)).toBe('72 rated films from 1980 to 2025; average 6.8; best film The Green Mile')
  })
})

describe('the career table', () => {
  test('lists every dated film with a link, score, votes and role', () => {
    const router = createMemoryRouter([{ path: '/', element: <CareerTable films={HANKS.films} /> }])
    render(<RouterProvider router={router} />)
    const table = screen.getByRole('table', { name: 'Career films' })
    expect(within(table).getAllByRole('row')).toHaveLength(HANKS.films.length + 1)
    const green = within(table).getByRole('link', { name: 'The Green Mile' })
    expect(green).toHaveAttribute('href', `/movies/${HANKS.best_film!.movie_id}`)
    expect(green.closest('tr')).toHaveTextContent(/1999The Green Mile8\.5[\d,]+as Paul Edgecomb · lead/)
  })
})
