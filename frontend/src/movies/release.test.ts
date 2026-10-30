import { expect, test } from 'vitest'

import { localToday, releaseLabel } from '@/movies/release'

test.each([
  ['2026-10-30', true, { kind: 'new', text: 'New', notRated: false, hideScore: false }],
  ['2026-10-16', false, { kind: 'new', text: 'New', notRated: true }],
  ['2026-10-15', false, { kind: null, text: null, hideScore: false, notRated: false }],
  ['2026-11-20', false, { kind: 'coming', text: 'Coming 20 Nov', hideScore: true }],
  ['2027-01-08', false, { kind: 'coming', text: 'Coming 8 Jan 2027', hideScore: true }],
  ['2026-10-31', true, { kind: 'coming', text: 'Coming 31 Oct' }],
  [null, true, { kind: null }],
  ['not a date', true, { kind: null }],
])('%s (score ok: %s)', (date, ok, want) => {
  expect(releaseLabel({ release_date: date, score_ok: ok }, '2026-10-30')).toMatchObject(want)
})

test('today is the visitor\'s calendar day', () => {
  expect(localToday(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05')
})
