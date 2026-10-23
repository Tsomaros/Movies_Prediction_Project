import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { CompareResponse, ModelCard, Options, Prediction, SweepResponse } from '@/api/client'
import { MONTH_VALUES, monthSweep, rankMonths } from '@/compare/sweep'
import {
  decodeVariants, driverChanges, encodeVariants, meaningful, PRESETS, presetAction, VARIANTS_PARAM, type Variant,
} from '@/compare/variants'
import { EXAMPLES } from '@/form/examples'
import { toApiBody } from '@/form/model'
import { encodeForm, toBase64Url } from '@/form/persist'
import compareJson from '@/test/compare.json'
import { mockFetch } from '@/test/fetch'
import modelCardJson from '@/test/model_card.json'
import optionsJson from '@/test/options.json'
import sweepJson from '@/test/sweep.json'
import { renderApp } from '@/test/render'

const options = optionsJson as Options
const card = modelCardJson as ModelCard
const COMPARE = compareJson.response as unknown as CompareResponse
const SWEEP = sweepJson as unknown as SweepResponse
const drama = EXAMPLES.find(e => e.key === 'small_drama')!
const blockbuster = EXAMPLES.find(e => e.key === 'franchise_blockbuster')!
const DRAMA = toApiBody(drama.form)
const BLOCKBUSTER = toApiBody(blockbuster.form)

// The variants the fixture was saved with (scratch script against the real API): holiday, unknown cast, PG-13
const SAVED: Variant[] = [
  { name: 'Holiday release', changes: { release_month: 12 } },
  { name: 'Unknown cast', changes: compareJson.request.variants[1] as Variant['changes'] },
  { name: 'PG-13 instead of R', changes: { certification: 'PG-13' } },
]

afterEach(() => vi.unstubAllGlobals())

function serve(compare: Parameters<typeof mockFetch>[0][string] = { body: COMPARE }) {
  return mockFetch({
    '/api/v1/meta/options': { body: options },
    '/api/v1/model-card': { body: card },
    '/api/v1/predict': { body: COMPARE.base },
    '/api/v1/predict/compare': compare,
    '/api/v1/predict/sweep': { body: SWEEP },
  })
}

const compareUrl = (variants: Variant[] = []) =>
  `/predict/compare?f=${encodeForm(drama.form)}${variants.length ? `&${VARIANTS_PARAM}=${encodeVariants(variants)}` : ''}`
const sent = (calls: ReturnType<typeof serve>['calls'], path: string) =>
  calls.filter(c => c.url.pathname === path).map(c => JSON.parse(String(c.init?.body)))

describe('variants', () => {
  test('every preset changes exactly one field, or says why it does not apply', () => {
    for (const [base, expected] of [
      [DRAMA, { holiday: { release_month: 12 }, franchise: 'pick', 'double-budget': 'Add a budget to the form first', 'pg13': { certification: 'PG-13' } }],
      [BLOCKBUSTER, { franchise: 'Already part of a franchise', 'double-budget': { budget: 600_000_000 }, pg13: 'hidden' }],
    ] as const) {
      for (const p of PRESETS) {
        const action = presetAction(p.id, base, options)
        if ('changes' in action) expect(Object.keys(action.changes)).toEqual([p.field])
        const want = (expected as Record<string, unknown>)[p.id]
        if (want === undefined) continue
        if (want === 'pick') expect(action).toEqual({ pick: 'franchise' })
        else if (want === 'hidden') expect(action).toEqual({ hidden: true })
        else if (typeof want === 'string') expect(action).toEqual({ disabled: want })
        else expect(action).toEqual({ changes: want })
      }
    }
    const unknown = presetAction('unknown-cast', DRAMA, options)
    expect('changes' in unknown && unknown.changes.actors).toEqual(DRAMA.actors!.map((_, i) => ({ name: `New actor ${i + 1}` })))
    expect(presetAction('holiday', { ...DRAMA, release_month: 12 }, options)).toEqual({ disabled: 'Already a December release' })
    expect(presetAction('double-budget', { ...DRAMA, budget: 6e8 }, options)).toEqual({ disabled: 'Twice the budget is over $1B' })
    expect(presetAction('holiday', DRAMA, options, [SAVED[0]])).toEqual({ disabled: 'Already added' })
  })

  test('the URL round trip, and malformed variants are dropped and counted', () => {
    expect(decodeVariants(encodeVariants(SAVED))).toEqual({ variants: SAVED, dropped: 0 })
    const bad = [
      SAVED[0], { name: 'two', changes: { runtime: 90, budget: 1e7 } }, { name: 'odd', changes: { genres: ['Drama'] } },
      { name: 'type', changes: { runtime: 'long' } }, { changes: { runtime: 90 } }, SAVED[1], SAVED[2], SAVED[0],
    ]
    expect(decodeVariants(toBase64Url(JSON.stringify(bad)))).toEqual({ variants: SAVED, dropped: 5 }) // 3 at most
    expect(decodeVariants('%%%')).toEqual({ variants: [], dropped: 1 })
    expect(decodeVariants(toBase64Url('{"a": 1}'))).toEqual({ variants: [], dropped: 1 })
    expect(decodeVariants(null)).toEqual({ variants: [], dropped: 0 })
  })

  test('"within the uncertainty" on both sides of the threshold', () => {
    const { revenue, revenue_estimated, budget, score } = card.uncertainty
    expect(meaningful('revenue', { ratio: revenue.ratio * 0.99 }, card, 'given')).toBe(false)
    expect(meaningful('revenue', { ratio: revenue.ratio * 1.01 }, card, 'given')).toBe(true)
    expect(meaningful('revenue', { ratio: 1 / (revenue.ratio * 1.01) }, card, 'given')).toBe(true) // down counts too
    expect(meaningful('revenue', { ratio: revenue.ratio * 1.01 }, card, 'estimated')).toBe(revenue.ratio * 1.01 >= revenue_estimated.ratio)
    expect(meaningful('budget', { ratio: budget.ratio * 0.99 }, card, 'given')).toBe(false)
    expect(meaningful('score', { points: -score.points * 0.99 }, card, 'given')).toBe(false)
    expect(meaningful('score', { points: -score.points * 1.01 }, card, 'given')).toBe(true)
    expect(meaningful('score', { points: 1 }, undefined, 'given')).toBeNull()
  })

  test('the drivers that moved, in words', () => {
    const [holiday] = COMPARE.variants
    const moved = driverChanges(COMPARE.base as Prediction, holiday.prediction as Prediction)
    expect(moved.some(m => m.startsWith('Release timing: now'))).toBe(true)
    expect(moved.every(m => / \(was .+\)$/.test(m))).toBe(true)
    expect(driverChanges(COMPARE.base as Prediction, COMPARE.base as Prediction)).toEqual([])
  })
})

describe('the compare page', () => {
  test('shows your film and each variant, greying changes within the uncertainty', async () => {
    const { calls } = serve()
    renderApp(compareUrl(SAVED))
    await waitFor(() => expect(screen.getAllByTestId('version')).toHaveLength(4))
    const [base, holiday, unknown] = screen.getAllByTestId('version')
    await within(holiday).findByText('Released in December')
    expect(within(base).getByText('As you planned it')).toBeInTheDocument()
    expect(await within(holiday).findByTestId('shift-revenue')).toHaveAttribute('data-meaningful', 'no')
    expect(within(holiday).getByTestId('shift-revenue')).toHaveTextContent('×1.3 · within the uncertainty')
    expect(within(unknown).getByTestId('shift-revenue')).toHaveAttribute('data-meaningful', 'yes')
    expect(within(unknown).getByTestId('shift-revenue')).toHaveTextContent('×0.3')
    expect(screen.getByTestId('threshold-note')).toHaveTextContent('×1.4 for box office')
    expect(sent(calls, '/api/v1/predict/compare')).toEqual([{ base: DRAMA, variants: SAVED.map(v => v.changes) }])
    expect(screen.getByText(/You're comparing 3 variants/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Box office side by side' })).toBeInTheDocument()
  })

  test('a preset adds a variant to the URL and the request; removing it takes it out', async () => {
    const { calls } = serve()
    const { router } = renderApp(compareUrl())
    await userEvent.click(await screen.findByRole('button', { name: 'Holiday release' }))
    expect(decodeVariants(new URLSearchParams(router.state.location.search).get(VARIANTS_PARAM)).variants)
      .toEqual([{ name: 'Holiday release', changes: { release_month: 12 } }])
    await waitFor(() => expect(sent(calls, '/api/v1/predict/compare')).toEqual([{ base: DRAMA, variants: [{ release_month: 12 }] }]))
    expect(screen.getByRole('button', { name: 'Holiday release' })).toBeDisabled() // already added
    await userEvent.click(screen.getByRole('button', { name: 'Remove Holiday release' }))
    expect(new URLSearchParams(router.state.location.search).has(VARIANTS_PARAM)).toBe(false)
  })

  test('one field changed by hand, checked against the API\'s limits first', async () => {
    serve()
    const { router } = renderApp(compareUrl())
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Or change one thing yourself' }), 'runtime')
    const box = screen.getByLabelText('New runtime')
    await userEvent.type(box, '20')
    await userEvent.click(screen.getByRole('button', { name: /Add variant/ }))
    expect(screen.getByRole('alert')).toHaveTextContent('The lowest allowed is 40')
    await userEvent.clear(box)
    await userEvent.type(box, '150')
    await userEvent.click(screen.getByRole('button', { name: /Add variant/ }))
    expect(decodeVariants(new URLSearchParams(router.state.location.search).get(VARIANTS_PARAM)).variants)
      .toEqual([{ name: '150 minutes long', changes: { runtime: 150 } }])
  })

  test.each([
    ['release_month', 'select', '12', { release_month: 12 }, 'Released in December'],
    ['release_year', 'type', '2028', { release_year: 2028 }, 'Released in 2028'],
    ['budget', 'type', '40', { budget: 40_000_000 }, 'Budget $40M'],
    ['certification', 'select', 'PG', { certification: 'PG' }, 'Rated PG'],
    ['language', 'select', 'fr', { language: 'fr' }, 'In French'],
  ])('a hand-made %s variant', async (field, how, value, changes, name) => {
    serve()
    const { router } = renderApp(compareUrl())
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Or change one thing yourself' }), field)
    const box = screen.getByLabelText(/^New /)
    if (how === 'select') await userEvent.selectOptions(box, value)
    else await userEvent.type(box, value)
    await userEvent.click(screen.getByRole('button', { name: /Add variant/ }))
    expect(decodeVariants(new URLSearchParams(router.state.location.search).get(VARIANTS_PARAM)).variants).toEqual([{ name, changes }])
  })

  test('the editor refuses a value the film already has, an empty one, and a duplicate', async () => {
    serve()
    renderApp(compareUrl([{ name: 'Rated PG', changes: { certification: 'PG' } }]))
    const field = await screen.findByRole('combobox', { name: 'Or change one thing yourself' })
    await userEvent.selectOptions(field, 'certification')
    const add = screen.getByRole('button', { name: /Add variant/ })
    await userEvent.click(add)
    expect(screen.getByRole('alert')).toHaveTextContent('Pick a value first')
    await userEvent.selectOptions(screen.getByLabelText('New rating'), 'R')
    await userEvent.click(add)
    expect(screen.getByRole('alert')).toHaveTextContent("That's what your film has already")
    await userEvent.selectOptions(screen.getByLabelText('New rating'), 'PG')
    await userEvent.click(add)
    expect(screen.getByRole('alert')).toHaveTextContent('You already have this variant')
    await userEvent.selectOptions(field, 'budget')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Leave the budget out (it is estimated)' }))
    await userEvent.click(add)
    expect(screen.getByRole('alert')).toHaveTextContent('The budget is already left out')
    await userEvent.selectOptions(field, 'director')
    await userEvent.click(add)
    expect(screen.getByRole('alert')).toHaveTextContent('Pick a director first')
  })

  test('a failed comparison or sweep offers a retry; a broken base link offers the form', async () => {
    mockFetch({
      '/api/v1/meta/options': { body: options }, '/api/v1/model-card': { body: card }, '/api/v1/predict': { body: COMPARE.base },
      '/api/v1/predict/compare': new TypeError('offline'), '/api/v1/predict/sweep': { status: 429, body: { detail: 'x' } },
    })
    const { unmount } = renderApp(compareUrl([SAVED[0]]))
    await waitFor(() => expect(screen.getAllByRole('alert').map(a => a.textContent).join(' ')).toContain("Can't reach the server"))
    expect(screen.getAllByRole('alert').map(a => a.textContent).join(' ')).toContain("You're going a bit fast")
    expect(screen.getAllByRole('button', { name: 'Try again' })).toHaveLength(2)
    unmount()
    renderApp('/predict/compare?f=nonsense')
    expect(await screen.findByText("This link doesn't hold a complete film plan.")).toBeInTheDocument()
  })

  test('"Make it a franchise" opens the franchise search', async () => {
    serve()
    renderApp(compareUrl())
    await userEvent.click(await screen.findByRole('button', { name: 'Make it a franchise' }))
    expect(screen.getByRole('combobox', { name: 'Or change one thing yourself' })).toHaveValue('franchise')
    expect(screen.getByPlaceholderText('Search franchises')).toBeInTheDocument()
  })

  test('a variant the API refuses is named on its column', async () => {
    serve({ status: 422, body: { detail: 'Some fields need fixing', errors: { 'variants.1.runtime': 'must be between 40 and 300' } } })
    renderApp(compareUrl([SAVED[0], { name: 'Too long', changes: { runtime: 999 } }]))
    const columns = await screen.findAllByTestId('version')
    expect(await within(columns[2]).findByRole('alert')).toHaveTextContent("This change can't be predicted: runtime must be between 40 and 300.")
    expect(within(columns[1]).getByRole('alert')).toHaveTextContent('Waiting for the other variants to be fixed.')
  })

  test('a broken link keeps what it can and says what it left out', async () => {
    serve()
    renderApp(`${compareUrl()}&${VARIANTS_PARAM}=${toBase64Url(JSON.stringify([SAVED[0], { name: 'x', changes: { nope: 1 } }]))}`)
    expect(await screen.findByTestId('link-notice')).toHaveTextContent("Part of this link couldn't be read: 1 variant was left out.")
    expect(await screen.findAllByTestId('version')).toHaveLength(2)
  })
})

describe('the release-month sweep', () => {
  test('asks for 12 months and ranks them, "about as good" within the threshold of the best', () => {
    expect(monthSweep(DRAMA)).toEqual({ form: DRAMA, field: 'release_month', values: MONTH_VALUES })
    const best = SWEEP.points.reduce((a, b) => (b.revenue.middle > a.revenue.middle ? b : a))
    const { best: top, aboutAsGood } = rankMonths(SWEEP.points, 1.2)
    expect(top).toBe(best.value)
    expect([...aboutAsGood].sort((a, b) => a - b)).toEqual(SWEEP.points
      .filter(p => p !== best && best.revenue.middle / p.revenue.middle < 1.2).map(p => p.value))
    expect(rankMonths(SWEEP.points, null).aboutAsGood.size).toBe(0)
  })

  test('the chart shows 12 months, your month and the best one', async () => {
    const { calls } = serve()
    renderApp(compareUrl())
    const summary = await screen.findByTestId('sweep-summary')
    expect(sent(calls, '/api/v1/predict/sweep')).toEqual([{ form: DRAMA, field: 'release_month', values: MONTH_VALUES }])
    expect(SWEEP.points).toHaveLength(12)
    expect(screen.getAllByTestId(/^month-\d+$/)).toHaveLength(12)
    expect(summary).toHaveTextContent('Best: December 2026')
    expect(summary).toHaveTextContent('Your month, October, is about as good') // a 1.3x lead is within the uncertainty here
    expect(screen.getByTestId('month-12')).toHaveAttribute('data-best', 'true')
    expect(screen.getByRole('table', { name: 'Expected box office by release month in 2026' })).toBeInTheDocument()
  })
})
