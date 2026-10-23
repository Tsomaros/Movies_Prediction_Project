import { describe, expect, test } from 'vitest'

import type { Options } from '@/api/client'
import { emptyForm, makeSchema, toApiBody, type FormValues } from '@/form/model'
import { VALID } from '@/test/forms'
import optionsJson from '@/test/options.json'

const options = optionsJson as Options
const schema = makeSchema(options.fields)

/** The message per field (first one), like the form shows them. */
function errorsOf(values: FormValues): Record<string, string> {
  const result = schema.safeParse(values)
  if (result.success) return {}
  const out: Record<string, string> = {}
  for (const issue of result.error.issues) out[issue.path.join('.')] ??= issue.message
  return out
}

describe('the rules mirror the contract', () => {
  test('a full form passes', () => {
    expect(errorsOf(VALID)).toEqual({})
  })

  test('a fresh form has runtime, release date and language filled in, and names the rest', () => {
    const fresh = emptyForm(new Date(2026, 9, 22))
    expect([fresh.runtime, fresh.release_month, fresh.release_year, fresh.language]).toEqual([110, 6, 2027, 'en'])
    expect(errorsOf(fresh)).toEqual({
      genres: 'Pick at least one genre', themes: 'Pick at least one theme', certification: 'Pick a rating',
      director: 'Pick a director or type a new name', actors: 'Add the 5 top-billed actors',
    })
  })

  test('cleared date, runtime and language are required again', () => {
    expect(errorsOf({ ...VALID, release_year: null, release_month: null, runtime: null, language: '' })).toEqual({
      release_year: 'Pick a release year', release_month: 'Pick a release month', runtime: 'Enter a runtime in minutes',
      language: 'Pick the original language',
    })
  })

  test.each([
    ['runtime', 'Runtime must be between 40 minutes and 300 minutes', { runtime: 39 }],
    ['runtime', 'Runtime must be between 40 minutes and 300 minutes', { runtime: 301 }],
    ['runtime', 'Runtime must be a whole number', { runtime: 90.5 }],
    ['budget', 'The budget must be between $1K and $1B', { budget: 999 }],
    ['budget', 'The budget must be between $1K and $1B', { budget: 1_000_000_001 }],
    ['genres', 'Pick at most 5 genres', { genres: ['Drama', 'Comedy', 'Crime', 'War', 'Music', 'History'] }],
    ['themes', 'Pick at most 5 themes', { themes: ['family', 'heist', 'sports', 'music', 'friendship', 'superhero'] }],
    ['certification', 'Pick a rating', { certification: 'X' }],
    ['language', 'Pick a language from the list', { language: 'english' }],
    ['countries', 'Pick countries from the list', { countries: ['us'] }],
    ['synopsis', 'Keep the synopsis under 2,000 characters', { synopsis: 'x'.repeat(2001) }],
    ['actors', 'Add 1 more actor (at least 5)', { actors: VALID.actors.slice(0, 4) }],
    ['actors', 'Add 3 more actors (at least 5)', { actors: VALID.actors.slice(0, 2) }],
    ['actors', 'The same actor is in the cast twice', { actors: [...VALID.actors.slice(0, 2), { id: 36592, name: 'Saoirse Ronan' }, ...VALID.actors.slice(3)] }],
    ['actors', 'The same actor is in the cast twice', { actors: [...VALID.actors.slice(0, 4), { id: null, name: 'ann newcomer' }] }],
  ] as const)('%s: "%s"', (field, message, change) => {
    expect(errorsOf({ ...VALID, ...change } as FormValues)[field]).toBe(message)
  })

  test('the edges are allowed', () => {
    expect(errorsOf({ ...VALID, runtime: 40, budget: 1000, synopsis: 'x'.repeat(2000) })).toEqual({})
    expect(errorsOf({ ...VALID, runtime: 300, budget: 1e9, actors: [...VALID.actors, ...Array(5).fill(null).map((_, i) => ({ id: null, name: `Extra ${i}` }))] })).toEqual({})
  })

  test('the limits come from the API: a different max changes the rule', () => {
    const fields = options.fields.map(f => (f.name === 'runtime' ? { ...f, max: 200 } : f))
    expect(makeSchema(fields).safeParse({ ...VALID, runtime: 250 }).success).toBe(false)
    expect(() => makeSchema(options.fields.filter(f => f.name !== 'budget'))).toThrow('no field "budget"')
  })
})

describe('the API body', () => {
  test('picked names keep their id, new names go by name (trimmed); empty optional fields are left out', () => {
    expect(toApiBody(VALID)).toEqual({
      genres: ['Drama'], themes: ['family'], release_year: 2026, release_month: 10, runtime: 105, language: 'en',
      certification: 'R', director: { id: 45400, name: 'Greta Gerwig' },
      actors: [{ id: 36592, name: 'Saoirse Ronan' }, { name: 'Ann Newcomer' }, { name: 'Bo Unknown' },
        { id: 1373737, name: 'Florence Pugh' }, { name: 'Cy Fresh' }],
    })
  })

  test('optional fields are sent when filled', () => {
    const body = toApiBody({
      ...VALID, companies: [{ id: 41077, name: 'A24', n_films: 72 }, { id: null, name: 'Tiny Films' }], countries: ['US', 'IE'],
      franchise: { id: null, name: 'New Saga' }, synopsis: '  Two sisters.  ', budget: 12_500_000,
    })
    expect(body).toMatchObject({
      companies: [{ id: 41077, name: 'A24' }, { name: 'Tiny Films' }], countries: ['US', 'IE'],
      franchise: { name: 'New Saga' }, synopsis: 'Two sisters.', budget: 12_500_000,
    })
  })

  test('a blank synopsis is left out', () => {
    expect(toApiBody({ ...VALID, synopsis: '   ' })).not.toHaveProperty('synopsis')
  })
})
