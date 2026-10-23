import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'

import type { Options } from '@/api/client'
import { EXAMPLES } from '@/form/examples'
import { toApiBody } from '@/form/model'
import { decodeForm, DRAFT_KEY, encodeForm, loadDraft, saveDraft } from '@/form/persist'
import { SAVE_MS } from '@/pages/Predict'
import { mockFetch } from '@/test/fetch'
import optionsJson from '@/test/options.json'
import predictionsJson from '@/test/predictions.json'
import { renderApp } from '@/test/render'

const options = optionsJson as Options

afterEach(() => vi.unstubAllGlobals())

function serve() {
  return mockFetch({ '/api/v1/meta/options': { body: options }, '/api/v1/predict': { body: predictionsJson.small_drama },
    '/api/v1/model-card': { status: 503, body: {} } })
}

async function openForm(path = '/predict') {
  const app = renderApp(path)
  await screen.findByRole('form', { name: 'Creator form' })
  return app
}

const posted = (calls: ReturnType<typeof serve>['calls']) =>
  calls.filter(c => c.url.pathname === '/api/v1/predict').map(c => JSON.parse(String(c.init?.body)))
const settle = () => new Promise(r => setTimeout(r, SAVE_MS + 100))

describe('examples', () => {
  test.each(EXAMPLES.map(e => [e.label, e] as const))('"%s" fills the form, and submitting sends its body and opens the result', async (label, example) => {
    const { calls } = serve()
    await openForm()
    await userEvent.click(screen.getByRole('button', { name: label }))
    expect(screen.getByRole('button', { name: `Remove ${example.form.director!.name}` })).toBeInTheDocument()
    expect(screen.getByText('Top-billed cast').parentElement).toHaveTextContent('(5/5–10)')
    await userEvent.click(screen.getByRole('button', { name: 'Predict' }))
    expect(await screen.findByTestId('card-revenue')).toHaveTextContent('$26M')
    expect(posted(calls)).toEqual([toApiBody(example.form)])
  })

  test('an example with optional fields opens "More details" and shows them', async () => {
    serve()
    await openForm()
    await userEvent.click(screen.getByRole('button', { name: 'Superhero sequel' }))
    expect(screen.getByRole('textbox', { name: 'Budget' })).toHaveValue('300')
    expect(screen.getByRole('button', { name: 'Remove The Avengers Collection' })).toBeVisible()
  })
})

describe('the URL and the draft', () => {
  test('the URL and the draft follow the form', async () => {
    serve()
    const { router } = await openForm()
    await userEvent.click(screen.getByRole('button', { name: 'Small indie drama' }))
    await settle()
    const inUrl = decodeForm(new URLSearchParams(router.state.location.search).get('f'))
    expect(inUrl).toEqual(EXAMPLES[1].form)
    expect(loadDraft()).toEqual(EXAMPLES[1].form)
  })

  test('a shared link opens that form', async () => {
    const { calls } = serve()
    await openForm(`/predict?f=${encodeForm(EXAMPLES[2].form)}`)
    expect(screen.getByText('Loaded from a shared link.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove Totally New Director' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Predict' }))
    await waitFor(() => expect(posted(calls)).toEqual([toApiBody(EXAMPLES[2].form)]))
  })

  test('a refresh brings the draft back', async () => {
    serve()
    saveDraft(EXAMPLES[1].form)
    await openForm()
    expect(screen.getByText('Your draft from last time is back.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove Greta Gerwig' })).toBeInTheDocument()
  })

  test('a link wins over the draft', async () => {
    serve()
    saveDraft(EXAMPLES[1].form)
    await openForm(`/predict?f=${encodeForm(EXAMPLES[0].form)}`)
    expect(screen.getByRole('button', { name: 'Remove Anthony Russo' })).toBeInTheDocument()
  })

  test('"Clear form" empties the form, the draft and the URL', async () => {
    serve()
    saveDraft(EXAMPLES[1].form)
    const { router } = await openForm(`/predict?f=${encodeForm(EXAMPLES[1].form)}`)
    await userEvent.click(screen.getByRole('button', { name: 'Clear form' }))
    await settle()
    expect(screen.getByRole('combobox', { name: 'Director' })).toBeInTheDocument()
    expect(screen.getByText('Genres').parentElement).toHaveTextContent('(0/5)')
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
    expect(router.state.location.search).toBe('')
  })

  test('"Copy link" copies the address with the form in it', async () => {
    serve()
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await openForm()
    await userEvent.click(screen.getByRole('button', { name: 'Horror, unknown cast' }))
    await userEvent.click(screen.getByRole('button', { name: 'Copy link' })) // at once, before the URL catches up
    const copied = new URL((writeText.mock.calls[0] as unknown as [string])[0])
    expect(decodeForm(copied.searchParams.get('f'))).toEqual(EXAMPLES[2].form)
  })
})
