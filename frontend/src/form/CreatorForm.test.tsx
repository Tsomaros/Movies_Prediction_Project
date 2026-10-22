import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { ApiError, type Options, type PredictForm } from '@/api/client'
import { CreatorForm } from '@/form/CreatorForm'
import { toApiBody, type FormValues } from '@/form/model'
import { mockFetch } from '@/test/fetch'
import { VALID } from '@/test/forms'
import optionsJson from '@/test/options.json'
import { renderApp } from '@/test/render'

const options = optionsJson as Options

afterEach(() => vi.unstubAllGlobals())

function renderForm(initial?: FormValues, onSubmit = vi.fn(async (_body: PredictForm) => {})) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><CreatorForm options={options} initial={initial} onSubmit={onSubmit} pending={false} /></QueryClientProvider>)
  return onSubmit
}

const submit = () => userEvent.click(screen.getByRole('button', { name: 'Predict' }))
const fieldError = (id: string) => document.getElementById(`${id}-error`)?.textContent
const people = (found: Record<string, { id: number; name: string; n_films: number }[]>) =>
  mockFetch({ '/api/v1/people': url => ({ body: found[url.searchParams.get('q') ?? ''] ?? [] }) })

describe('validation blocks a bad form', () => {
  test('a fresh form shows what is left to fill and sends nothing', async () => {
    const onSubmit = renderForm()
    await submit()
    expect(await screen.findByText('Pick at least one genre')).toBeInTheDocument()
    expect(fieldError('f-certification')).toBe('Pick a rating')
    expect(fieldError('f-director')).toBe('Pick a director or type a new name')
    expect(fieldError('f-actors')).toBe('Add the 5 top-billed actors')
    expect(fieldError('f-runtime')).toBeUndefined() // prefilled: 110 minutes
    expect(onSubmit).not.toHaveBeenCalled()
  })

  test('the first field with an error gets the focus', async () => {
    renderForm({ ...VALID, genres: [] })
    await submit()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Action' })).toHaveFocus())
  })

  test('4 actors, runtime 30 and a $500 budget each get their message; "More details" opens for the budget', async () => {
    const onSubmit = renderForm({ ...VALID, actors: VALID.actors.slice(0, 4), runtime: 30, budget: 500 })
    await submit()
    expect(await screen.findByText('Add 1 more actor (at least 5)')).toBeInTheDocument()
    expect(fieldError('f-runtime')).toBe('Runtime must be between 40 minutes and 300 minutes')
    expect(fieldError('f-budget')).toBe('The budget must be between $1K and $1B')
    expect(screen.getByRole('textbox', { name: 'Budget' })).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  test('a valid form is sent as the API body', async () => {
    const onSubmit = renderForm(VALID)
    await submit()
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(toApiBody(VALID)))
  })

  test('fixing a field clears its message as you go', async () => {
    renderForm({ ...VALID, runtime: 30 })
    await submit()
    expect(await screen.findByText(/Runtime must be between/)).toBeInTheDocument()
    const runtime = screen.getByRole('spinbutton', { name: 'Runtime' })
    await userEvent.clear(runtime)
    await userEvent.type(runtime, '95')
    await waitFor(() => expect(screen.queryByText(/Runtime must be between/)).not.toBeInTheDocument())
  })
})

describe('inputs', () => {
  test('genre chips toggle, count in the label, and stop at 5', async () => {
    renderForm()
    const group = screen.getByRole('group', { name: /Genres/ })
    for (const g of ['Action', 'Comedy', 'Crime', 'Drama', 'War']) await userEvent.click(within(group).getByRole('button', { name: g }))
    expect(screen.getByText('Genres').parentElement).toHaveTextContent('Genres (5/5)')
    expect(within(group).getByRole('button', { name: 'Music' })).toBeDisabled()
    await userEvent.click(within(group).getByRole('button', { name: 'Drama' }))
    expect(within(group).getByRole('button', { name: 'Music' })).toBeEnabled()
  })

  test('the budget is typed in millions and sent in dollars; empty means "estimate it"', async () => {
    const onSubmit = renderForm(VALID)
    await userEvent.click(screen.getByRole('button', { name: /More details/ }))
    const budget = screen.getByRole('textbox', { name: 'Budget' })
    await userEvent.type(budget, '12.5')
    expect(budget).toHaveValue('12.5')
    expect(screen.getByText('= $12.5M')).toBeInTheDocument()
    expect(screen.getByText(/Leave it empty and we'll estimate it/)).toBeInTheDocument()
    await submit()
    await waitFor(() => expect(onSubmit.mock.calls[0][0]).toMatchObject({ budget: 12_500_000 }))
  })

  test('a budget set from outside shows in millions', () => {
    renderForm({ ...VALID, budget: 2_000_000 })
    expect(screen.getByRole('textbox', { name: 'Budget' })).toHaveValue('2')
  })

  test('the synopsis counts characters', async () => {
    renderForm()
    await userEvent.click(screen.getByRole('button', { name: /More details/ }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Synopsis' }), 'Two sisters run a bakery.')
    expect(screen.getByText('25 / 2,000')).toBeInTheDocument()
  })
})

describe('typing a name', () => {
  test('suggestions show film counts; Enter picks the top one; the cast is numbered chips', async () => {
    people({ sao: [{ id: 36592, name: 'Saoirse Ronan', n_films: 28 }, { id: 2, name: 'Saoirse Hayden', n_films: 1 }] })
    renderForm()
    const box = screen.getByRole('combobox', { name: /Top-billed cast/ })
    await userEvent.type(box, 'sao')
    const top = await screen.findByRole('option', { name: /Saoirse Ronan/ })
    expect(top).toHaveTextContent('28 films')
    expect(top).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('option', { name: /Use “sao” as a new person/ })).toBeInTheDocument()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('list', { name: 'Chosen' })).toHaveTextContent('1. Saoirse Ronan28 films')
    expect(box).toHaveValue('')
    expect(screen.getByText('Top-billed cast').parentElement).toHaveTextContent('(1/5–10)')
  })

  test('Enter before the suggestions arrive does nothing, and never submits the form', async () => {
    people({ sao: [{ id: 36592, name: 'Saoirse Ronan', n_films: 28 }] })
    const onSubmit = renderForm()
    await userEvent.type(screen.getByRole('combobox', { name: /Top-billed cast/ }), 'sao{Enter}')
    expect(screen.queryByRole('list', { name: 'Chosen' })).not.toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
    expect(await screen.findByRole('option', { name: /Saoirse Ronan/ })).toBeInTheDocument()
  })

  test('arrow down reaches "new person"; a picked name leaves the suggestions', async () => {
    people({ ann: [{ id: 7, name: 'Ann Known', n_films: 3 }] })
    renderForm()
    const box = screen.getByRole('combobox', { name: /Top-billed cast/ })
    await userEvent.type(box, 'ann')
    await screen.findByRole('option', { name: /Ann Known/ })
    await userEvent.keyboard('{ArrowDown}{Enter}')
    expect(screen.getByRole('list', { name: 'Chosen' })).toHaveTextContent('1. annnew')
    await userEvent.type(box, 'ann')
    await screen.findByRole('option', { name: /Ann Known/ })
    expect(screen.queryByRole('option', { name: /Use “ann”/ })).not.toBeInTheDocument() // already in the cast
  })

  test('chips can be removed, and the box closes at 10 actors', async () => {
    const ten = Array.from({ length: 10 }, (_, i) => ({ id: null, name: `Actor ${i + 1}` }))
    renderForm({ ...VALID, actors: ten })
    expect(screen.getByRole('combobox', { name: /Top-billed cast/ })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Remove Actor 3' }))
    expect(screen.getByRole('combobox', { name: /Top-billed cast/ })).toBeEnabled()
    expect(screen.getByRole('list', { name: 'Chosen' })).toHaveTextContent('3. Actor 4')
  })

  test('the director becomes a chip, and removing it brings the box back', async () => {
    people({ jane: [] })
    renderForm()
    await userEvent.type(screen.getByRole('combobox', { name: 'Director' }), 'jane')
    await userEvent.click(await screen.findByRole('option', { name: /Use “jane” as a new person/ }))
    expect(screen.getByRole('button', { name: 'Remove jane' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove jane' }))
    expect(screen.getByRole('combobox', { name: 'Director' })).toBeInTheDocument()
  })

  test('typed text that is not picked gets a hint and is not sent', async () => {
    people({})
    renderForm()
    await userEvent.type(screen.getByRole('combobox', { name: 'Director' }), 'Half Typed')
    await userEvent.tab()
    expect(screen.getByText(/Typed text alone isn't used/)).toBeInTheDocument()
  })
})

describe('the page', () => {
  test('loads the options into the form; submitting a fresh form sends nothing', async () => {
    const { calls } = mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/predict': { body: {} } })
    renderApp('/predict')
    expect(await screen.findByText('Loading the form…')).toBeInTheDocument()
    expect(await screen.findByRole('form', { name: 'Creator form' })).toBeInTheDocument()
    await submit()
    expect(await screen.findByText('Pick at least one genre')).toBeInTheDocument()
    expect(calls.filter(c => c.url.pathname === '/api/v1/predict')).toHaveLength(0)
  })

  test("the form says when the options can't load, with a retry", async () => {
    mockFetch({ '/api/v1/meta/options': { status: 500 } })
    renderApp('/predict')
    expect(await screen.findByText(/The form couldn't load/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('server errors', () => {
  test("a 422 puts the API's messages on the fields, and shows the rest above the button", async () => {
    const onSubmit = vi.fn(async () => {
      throw new ApiError('validation', 'Some fields need fixing',
        { fieldErrors: { runtime: 'must be between 40 and 300', budget: 'must be a number', mystery: 'odd' } })
    })
    renderForm(VALID, onSubmit)
    await submit()
    await waitFor(() => expect(fieldError('f-runtime')).toBe('must be between 40 and 300'))
    expect(fieldError('f-budget')).toBe('must be a number')
    expect(screen.getByRole('textbox', { name: 'Budget' })).toBeVisible() // "More details" opened for it
    expect(screen.getByText('mystery: odd')).toBeInTheDocument()
  })
})

describe('language and countries', () => {
  test('the language list shows names and film counts, and can be searched', async () => {
    const onSubmit = renderForm(VALID)
    await userEvent.click(screen.getByRole('combobox', { name: /Original language/ }))
    await userEvent.type(screen.getByPlaceholderText('Search languages…'), 'fren')
    const french = await screen.findByRole('option', { name: /French/ })
    expect(french).toHaveTextContent(/French[\d,]+ films/)
    await userEvent.click(french)
    expect(screen.getByRole('combobox', { name: /Original language/ })).toHaveTextContent('French')
    await submit()
    await waitFor(() => expect(onSubmit.mock.calls[0][0]).toMatchObject({ language: 'fr' }))
  })

  test('countries are added as chips, removed, and stop at 5', async () => {
    const onSubmit = renderForm(VALID)
    await userEvent.click(screen.getByRole('button', { name: /More details/ }))
    const pick = async (name: RegExp) => {
      await userEvent.click(screen.getByRole('combobox', { name: /Production countries/ }))
      await userEvent.click(await screen.findByRole('option', { name }))
    }
    for (const name of [/^United States/, /^Ireland/, /^France/, /^Germany/, /^Japan/]) await pick(name)
    expect(screen.getByRole('combobox', { name: /Production countries/ })).toBeDisabled()
    expect(screen.getByText('Production countries').parentElement).toHaveTextContent('(5/5)')
    await userEvent.click(screen.getByRole('button', { name: 'Remove Germany' }))
    expect(screen.getByRole('combobox', { name: /Production countries/ })).toBeEnabled()
    await submit()
    await waitFor(() => expect(onSubmit.mock.calls[0][0]).toMatchObject({ countries: ['US', 'IE', 'FR', 'JP'] }))
  })
})
