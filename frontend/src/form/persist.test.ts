import { afterEach, describe, expect, test, vi } from 'vitest'

import type { Options, PredictForm } from '@/api/client'
import { EXAMPLES } from '@/form/examples'
import { emptyForm, makeSchema, toApiBody } from '@/form/model'
import {
  clearDraft, decodeForm, DRAFT_KEY, encodeForm, loadDraft, parseForm, readForm, saveDraft, startingForm, toBase64Url,
} from '@/form/persist'
import { VALID } from '@/test/forms'
import optionsJson from '@/test/options.json'
import golden from '../../../tests/golden/forms.json'

const schema = makeSchema((optionsJson as Options).fields)

/** The golden forms write a picked person as its id and a new one as its name; ours send {id, name} or {name}. */
function asGolden(body: PredictForm): Record<string, unknown> {
  const ref = (r: unknown) => {
    const { id, name } = r as { id?: number; name?: string }
    return id !== undefined ? id : name
  }
  const out: Record<string, unknown> = { ...body, director: ref(body.director), actors: (body.actors ?? []).map(ref) }
  if (body.companies) out.companies = (body.companies as unknown[]).map(ref)
  if (body.franchise) out.franchise = ref(body.franchise)
  return out
}

describe('examples', () => {
  test('there are the plan\'s three: a franchise, a low budget and new people', () => {
    expect(EXAMPLES.map(e => e.label)).toEqual(['Superhero sequel', 'Small indie drama', 'Horror, unknown cast'])
  })

  test.each(EXAMPLES.map(e => [e.label, e] as const))('%s fills every required field and passes the rules', (_, example) => {
    expect(schema.safeParse(example.form).success).toBe(true)
  })

  test.each(EXAMPLES.map(e => [e.key, e] as const))('%s sends exactly the golden form', (key, example) => {
    expect(asGolden(toApiBody(example.form))).toEqual((golden.forms as Record<string, unknown>)[key])
  })
})

describe('the form in the URL', () => {
  test.each(EXAMPLES.map(e => [e.label, e] as const))('%s round-trips', (_, example) => {
    const text = encodeForm(example.form)
    expect(text).toMatch(/^[A-Za-z0-9_-]+$/) // safe in a URL as is
    expect(decodeForm(text)).toEqual(example.form)
  })

  test('non-ASCII names survive (Timothée)', () => {
    expect(decodeForm(encodeForm(EXAMPLES[1].form))?.actors[2].name).toBe('Timothée Chalamet')
  })

  test.each([null, '', 'not-base64!', encodeForm([] as never), 'eyJ4IjoxfQ' /* {"x":1} */])('%j is not a form', text => {
    expect(decodeForm(text)).toBeNull()
  })

  test('a field of the wrong type keeps the fresh value; unknown keys are dropped', () => {
    const form = parseForm({ ...VALID, runtime: 'long', actors: [{ id: -3, name: 'x' }], evil: '<script>' })
    expect(form?.runtime).toBe(emptyForm().runtime)
    expect(form?.actors).toEqual([])
    expect(form).not.toHaveProperty('evil')
    expect(form?.director).toEqual(VALID.director)
  })
})

describe('the draft', () => {
  afterEach(() => vi.restoreAllMocks())

  test('saves, loads and clears', () => {
    saveDraft(VALID)
    expect(loadDraft()).toEqual(VALID)
    clearDraft()
    expect(loadDraft()).toBeNull()
  })

  test('blocked storage means "no draft", never an error', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('SecurityError') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('QuotaExceeded') })
    expect(() => saveDraft(VALID)).not.toThrow()
    expect(loadDraft()).toBeNull()
  })

  test('a broken draft is ignored', () => {
    localStorage.setItem(DRAFT_KEY, '{not json')
    expect(loadDraft()).toBeNull()
  })
})

describe('a link edited by hand', () => {
  test('keeps the readable fields and names the ones it reset', () => {
    const edited = { ...EXAMPLES[0].form, runtime: 'long', director: { id: 'x' }, unknown: 1 }
    const read = readForm(toBase64Url(JSON.stringify(edited)))
    expect(read?.dropped).toEqual(['runtime', 'director'])
    expect(read?.form.runtime).toBe(emptyForm().runtime)
    expect(read?.form.genres).toEqual(EXAMPLES[0].form.genres)
    expect(startingForm(`?f=${toBase64Url(JSON.stringify(edited))}`).dropped).toEqual(['runtime', 'director'])
    expect(readForm(encodeForm(EXAMPLES[0].form))?.dropped).toEqual([])
  })
})

describe('where a page load starts', () => {
  test('the URL wins over the draft, the draft over a fresh form', () => {
    saveDraft(EXAMPLES[1].form)
    expect(startingForm(`?f=${encodeForm(EXAMPLES[0].form)}`)).toEqual({ form: EXAMPLES[0].form, dropped: [], source: 'link' })
    expect(startingForm('')).toEqual({ form: EXAMPLES[1].form, dropped: [], source: 'draft' })
    expect(startingForm('?f=garbage')).toEqual({ form: EXAMPLES[1].form, dropped: [], source: 'draft' })
    clearDraft()
    expect(startingForm('').source).toBe('new')
  })
})
