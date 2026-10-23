import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { ApiError, type ModelCard, type Options, type Prediction } from '@/api/client'
import { EXAMPLES } from '@/form/examples'
import { changedFields, toApiBody } from '@/form/model'
import { BASE_PARAM, encodeForm } from '@/form/persist'
import { breakEven, factor, money, moneyAxis, points, signedPoints } from '@/result/format'
import { mockFetch } from '@/test/fetch'
import modelCardJson from '@/test/model_card.json'
import optionsJson from '@/test/options.json'
import predictionsJson from '@/test/predictions.json'
import { renderApp } from '@/test/render'

const options = optionsJson as Options
const card = modelCardJson as ModelCard
const PREDICTIONS = predictionsJson as unknown as Record<string, Prediction>
const byKey = Object.fromEntries(EXAMPLES.map(e => [e.key, e]))

afterEach(() => vi.unstubAllGlobals())

/** The API with the real answers for the three examples (by the form sent) and the real model card. */
function serve(overrides: Record<string, Parameters<typeof mockFetch>[0][string]> = {}) {
  return mockFetch({
    '/api/v1/meta/options': { body: options },
    '/api/v1/model-card': { body: card },
    '/api/v1/predict': (_url, init) => {
      const sent = JSON.parse(String(init?.body))
      const example = EXAMPLES.find(e => JSON.stringify(toApiBody(e.form)) === JSON.stringify(sent))
      return example ? { body: PREDICTIONS[example.key] } : { status: 422, body: { detail: 'Some fields need fixing', errors: {} } }
    },
    ...overrides,
  })
}

const resultUrl = (key: string, base?: string) =>
  `/predict/result?f=${encodeForm(byKey[key].form)}${base ? `&${BASE_PARAM}=${encodeForm(byKey[base].form)}` : ''}`
const posts = (calls: ReturnType<typeof serve>['calls']) => calls.filter(c => c.url.pathname === '/api/v1/predict').length

async function openResult(key: string, base?: string) {
  const app = renderApp(resultUrl(key, base))
  await screen.findByTestId('card-revenue')
  return app
}

describe('format', () => {
  test('money has two significant figures, like the API', () => {
    expect([1580693165, 406875181, 26527963, 2e6, 38123, 999].map(money)).toEqual(['$1.6B', '$410M', '$27M', '$2M', '$38K', '$1K'])
    expect(money(180783434)).toBe('$180M')
  })

  test('scores, factors and point changes', () => {
    expect(points(7.357)).toBe('7.4')
    expect([1.25, 0.5, 12.4].map(factor)).toEqual(['×1.3', '×0.5', '×12'])
    expect([0.24, -0.31, -0.04].map(signedPoints)).toEqual(['+0.2', '−0.3', '0.0'])
  })

  test('break-even is 2-2.5x the budget', () => {
    expect([breakEven(1.9e6, 1e6), breakEven(2.2e6, 1e6), breakEven(3e6, 1e6)]).toEqual(['below', 'within', 'above'])
  })

  test('the money axis covers every value, with ticks at powers of ten', () => {
    const { at, ticks } = moneyAxis([2e5, 7e6, 1.4e7])
    expect(at(2e5)).toBeGreaterThan(0)
    expect(at(1.4e7)).toBeLessThan(100)
    expect(ticks).toEqual([3e5, 1e6, 3e6, 1e7]) // only two powers of ten fit, so 3s are added
    expect(moneyAxis([1e5, 1e9]).ticks).toEqual([1e5, 1e6, 1e7, 1e8, 1e9])
  })
})

describe('the golden examples', () => {
  test('superhero sequel: ranges, budget comparison, break-even above, its notes', async () => {
    serve()
    await openResult('franchise_blockbuster')
    expect(screen.getByRole('heading', { level: 1, name: 'Your prediction' })).toBeInTheDocument()
    expect(screen.getByText(/Action, Adventure, Science Fiction · May 2027 · directed by Anthony Russo/)).toBeInTheDocument()
    expect(screen.getByTestId('card-revenue')).toHaveTextContent('$1.6B')
    expect(screen.getByTestId('card-revenue')).toHaveTextContent('Likely $500M–$3.6B')
    expect(screen.getByTestId('card-budget')).toHaveTextContent('$410M')
    expect(screen.getByTestId('card-budget')).toHaveTextContent('Budget typical for similar films')
    expect(screen.getByTestId('card-budget')).toHaveTextContent('Your budget of $300M is within what similar films usually cost.')
    expect(screen.getByTestId('card-score')).toHaveTextContent('7.4')
    expect(screen.queryByText('Rough estimate')).toBeNull()
    expect(screen.queryByText('Budget estimated')).toBeNull()
    expect(screen.getByTestId('break-even-text')).toHaveTextContent('($600M–$750M): 2–2.5× your budget')
    expect(screen.getByTestId('break-even-text')).toHaveTextContent('above the break-even zone')
    expect(screen.getByTestId('note-big_budget')).toBeInTheDocument()
    expect(screen.getByTestId('note-future_release')).toBeInTheDocument()
    expect(screen.getByTestId('note-score')).toHaveTextContent('settled score')
    expect(screen.getByTestId('limitations')).toHaveTextContent('Estimates, not guarantees.')
  })

  test('small drama: budget estimated, rough estimates, "not reported" money, break-even below', async () => {
    serve()
    await openResult('small_drama')
    expect(screen.getByText('Budget estimated')).toBeInTheDocument()
    expect(screen.getByTestId('card-revenue')).toHaveTextContent('uses the estimated budget of $27M')
    expect(screen.getAllByText('Rough estimate')).toHaveLength(2)
    expect(screen.getByTestId('card-budget')).toHaveTextContent('Estimated budget')
    expect(screen.getByTestId('break-even-text')).toHaveTextContent('2–2.5× the estimated budget')
    expect(screen.getByTestId('break-even-text')).toHaveTextContent('below the break-even zone')
    expect(screen.getAllByText('not reported')).toHaveLength(4)
    expect(screen.getByTestId('note-new_actors')).toBeInTheDocument()
  })

  test('unknown cast: the new-person notes and every empty-field note', async () => {
    serve()
    await openResult('unknown_cast')
    for (const code of ['new_director', 'new_actors', 'no_country', 'no_studio', 'future_release'])
      expect(screen.getByTestId(`note-${code}`)).toBeInTheDocument()
    expect(screen.getByTestId('card-revenue')).toHaveTextContent('$1M')
    expect(screen.getByTestId('card-revenue')).toHaveTextContent('Likely $38K–$14M')
  })

  test('five comparable films with posters, real numbers, why tags and links to their pages', async () => {
    serve()
    await openResult('franchise_blockbuster')
    const section = screen.getByRole('region', { name: 'Films like yours' })
    const items = within(section).getAllByRole('link')
    expect(items).toHaveLength(5)
    expect(items[0]).toHaveAttribute('href', '/movies/298618')
    expect(within(section).getByRole('img', { name: 'Poster of The Flash' })).toHaveAttribute('loading', 'lazy')
    expect(within(section).getAllByRole('list', { name: 'Why similar' })[0]).toHaveTextContent('Similar budget')
    expect(section).toHaveTextContent('$2.6B') // Infinity War's real revenue
  })

  test('drivers open on revenue, and the tabs switch target', async () => {
    serve()
    await openResult('franchise_blockbuster')
    const drivers = screen.getByRole('region', { name: 'What drives these estimates' })
    expect(within(drivers).getByRole('tab', { name: 'Revenue' })).toHaveAttribute('aria-selected', 'true')
    expect(within(drivers).getByText('A budget of $300M strongly raises the expected revenue.')).toBeVisible()
    await userEvent.click(within(drivers).getByRole('tab', { name: 'Budget' }))
    expect(within(drivers).getByText('Marvel Studios as the studio strongly raises the expected budget.')).toBeVisible()
    expect(within(drivers).getAllByText('Nothing notable.').some(e => e.checkVisibility?.() ?? true)).toBe(true)
  })

  test('the accuracy panel shows the model card for the revenue mode in use', async () => {
    serve()
    await openResult('small_drama') // budget estimated
    const panel = await screen.findByTestId('accuracy')
    const t = card.test.targets
    expect(panel).toHaveTextContent(`Revenue (budget estimated)${Math.round(t.revenue_estimated.model.coverage * 100)}% of 1,485`)
    expect(panel).toHaveTextContent(`Budget${Math.round(t.budget.model.coverage * 100)}% of 1,964off by ×2 (×3.5)`)
    expect(panel).toHaveTextContent('Audience score81% of 7,461off by 0.5 points (0.6 points)')
    expect(panel).toHaveTextContent(`Audience score${Math.round(card.holdout.targets.score.model.coverage * 100)}% of 190`)
    expect(panel).toHaveTextContent('built from 79,199 films released 1960–2025')
    expect(within(panel).getByRole('link', { name: 'Read how it was tested' })).toHaveAttribute('href', expect.stringContaining('#readme'))
  })
})

describe('getting there and moving on', () => {
  test('submitting the form opens the results page with the cached answer (one request)', async () => {
    const { calls } = serve()
    const { router } = renderApp('/predict')
    await screen.findByRole('form', { name: 'Creator form' })
    await userEvent.click(screen.getByRole('button', { name: 'Superhero sequel' }))
    await userEvent.click(screen.getByRole('button', { name: 'Predict' }))
    expect(await screen.findByTestId('card-revenue')).toHaveTextContent('$1.6B')
    expect(router.state.location.pathname).toBe('/predict/result')
    expect(posts(calls)).toBe(1)
  })

  test('a shared result link predicts once', async () => {
    const { calls } = serve()
    await openResult('unknown_cast')
    expect(posts(calls)).toBe(1)
  })

  test('skeletons hold the layout while the prediction loads', async () => {
    const { fetch } = serve()
    const answered = fetch.getMockImplementation()!
    fetch.mockImplementation(async (input, init) =>
      String(input).endsWith('/predict') ? new Promise<Response>(() => {}) : answered(input, init))
    renderApp(resultUrl('unknown_cast'))
    expect(await screen.findByText('Running the models…')).toBeInTheDocument()
    expect(document.querySelector('[aria-busy="true"]')?.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(5)
  })

  test('the actions: edit, try a variation, copy the link, print', async () => {
    serve()
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    const print = vi.fn()
    vi.stubGlobal('print', print)
    const { router } = await openResult('small_drama')
    const actions = screen.getByRole('toolbar', { name: 'Result actions' })
    await userEvent.click(within(actions).getByRole('button', { name: /Copy link/ }))
    expect(writeText).toHaveBeenCalledWith(window.location.href)
    await userEvent.click(within(actions).getByRole('button', { name: /Print/ }))
    expect(print).toHaveBeenCalled()
    await userEvent.click(within(actions).getByRole('link', { name: /Try a variation/ }))
    await screen.findByTestId('variation-hint')
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get(BASE_PARAM)).toBe(params.get('f'))
    expect(screen.getByRole('button', { name: 'Remove Greta Gerwig' })).toBeInTheDocument() // the form is filled in
  })

  test('a variation shows what changed and how far the expected values moved', async () => {
    serve()
    await openResult('franchise_blockbuster', 'small_drama')
    const strip = await screen.findByTestId('variation')
    const [now, before] = [PREDICTIONS.franchise_blockbuster, PREDICTIONS.small_drama]
    await waitFor(() => expect(strip).toHaveTextContent(`Revenue: ${factor(now.revenue.middle / before.revenue.middle)}`))
    expect(strip).toHaveTextContent(`(${money(before.revenue.middle)} → ${money(now.revenue.middle)})`)
    expect(strip).toHaveTextContent(`Score: ${signedPoints(now.score.middle - before.score.middle)}`)
    expect(strip).toHaveTextContent('You changed the genres, themes')
  })

  test('changedFields names only the fields that differ', () => {
    const a = toApiBody(EXAMPLES[0].form)
    expect(changedFields(a, a)).toEqual([])
    expect(changedFields(a, { ...a, budget: 1e8 })).toEqual(['budget'])
    const { budget: _, ...noBudget } = a
    expect(changedFields(a, { ...noBudget, release_month: 12 })).toEqual(['release month', 'budget'])
  })
})

describe('when things go wrong', () => {
  test('a link without a complete form says so and offers the form', async () => {
    serve()
    renderApp('/predict/result?f=nonsense')
    expect(await screen.findByText("This link doesn't hold a complete film plan.")).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Plan a film' })).toHaveAttribute('href', '/predict')
  })

  test('too many requests: the message, and editing still works', async () => {
    serve({ '/api/v1/predict': { status: 429, body: { detail: 'Too many' }, headers: { 'Retry-After': '30' } } })
    renderApp(resultUrl('small_drama'))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Too many predictions – try again in a minute.')
    expect(within(alert).getByRole('link', { name: 'Edit the inputs' })).toHaveAttribute('href', expect.stringContaining('/predict?f='))
  })

  test('a network failure offers a retry that works', async () => {
    let fail = true
    serve({ '/api/v1/predict': () => (fail ? new TypeError('Failed to fetch') : { body: PREDICTIONS.small_drama }) })
    renderApp(resultUrl('small_drama'))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(new ApiError('network', "Can't reach the server. Check your connection and try again.").message)
    fail = false
    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
    expect(await screen.findByTestId('card-revenue')).toHaveTextContent('$26M')
  })

  test('a model card that fails to load leaves the rest of the page working', async () => {
    serve({ '/api/v1/model-card': { status: 503, body: { detail: 'stale' } } })
    await openResult('franchise_blockbuster')
    expect(await screen.findByText("The accuracy numbers couldn't load right now.")).toBeInTheDocument()
    expect(screen.getByTestId('card-score')).toHaveTextContent('7.4')
  })
})
