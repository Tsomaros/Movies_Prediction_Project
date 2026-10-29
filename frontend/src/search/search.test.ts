import { afterEach, expect, test, vi } from 'vitest'

import {
  isTypingTarget, modeFromLocation, readStoredMode, resultsUrl, rolesLine, storeMode, usableQuery,
} from '@/search/search'

afterEach(() => vi.restoreAllMocks())

test.each([['a', null], ['  ', null], ['"*', null], ['é', null], ['to', 'to'], ['  tom ha ', 'tom ha'], ['7a', '7a']])(
  'usableQuery(%j)', (q, out) => expect(usableQuery(q)).toBe(out))

test('a results page sets the mode; any other page leaves it to the stored one', () => {
  expect(modeFromLocation('/browse')).toBe('movies')
  expect(modeFromLocation('/people')).toBe('people')
  expect(modeFromLocation('/people/31')).toBeNull()
  expect(modeFromLocation('/predict')).toBeNull()
})

test('the stored mode defaults to movies and survives blocked storage', () => {
  expect(readStoredMode()).toBe('movies')
  storeMode('people')
  expect(readStoredMode()).toBe('people')
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  expect(readStoredMode()).toBe('movies')
  expect(() => storeMode('people')).not.toThrow()
})

test('the results address keeps browse filters, starts at page 1 and encodes the text', () => {
  expect(resultsUrl('movies', 'nolan', new URLSearchParams('genre=Drama&page=3&q=old'))).toBe('/browse?genre=Drama&q=nolan')
  expect(resultsUrl('people', ' tom hanks ')).toBe('/people?q=tom%20hanks')
  expect(resultsUrl('movies', 'amélie & co')).toBe('/browse?q=am%C3%A9lie%20%26%20co')
})

test('typing targets are inputs, text areas, selects and editable elements', () => {
  expect(isTypingTarget(document.createElement('input'))).toBe(true)
  expect(isTypingTarget(document.createElement('textarea'))).toBe(true)
  expect(isTypingTarget(document.createElement('select'))).toBe(true)
  const div = document.createElement('div')
  div.setAttribute('contenteditable', 'true')
  expect(isTypingTarget(div)).toBe(true)
  expect(isTypingTarget(document.body)).toBe(false)
  expect(isTypingTarget(null)).toBe(false)
})

test('the roles line names one role with its films, or several roles', () => {
  expect(rolesLine([{ role: 'actor', n_films: 42 }])).toBe('Actor · 42 films')
  expect(rolesLine([{ role: 'writer', n_films: 1 }])).toBe('Writer · 1 film')
  expect(rolesLine([{ role: 'actor', n_films: 9 }, { role: 'director', n_films: 2 }])).toBe('Actor, Director')
})
