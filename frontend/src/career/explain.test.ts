import { describe, expect, test } from 'vitest'

import type { CareerResponse } from '@/api/client'
import { explainText } from '@/career/explain'
import hanksJson from '@/test/career_hanks.json'

const F = { n_rated: 23, own_avg: 6.9, own_share: 0.82, db_avg: 6.3, mid: 6.8 }

describe('the "How is this calculated?" paragraph', () => {
  test("uses the person's numbers and the backtest hit rate, exactly as the spec words it", () => {
    expect(explainText(F, { coverage: 0.81 }, 8)).toBe(
      'Based on 23 rated films. Recent films count more: a film from 8 years before the latest counts half. '
      + 'Their weighted average is 6.9; with this many films we trust it 82% and the database average (6.3) 18%, '
      + 'giving 6.8. The range is wider for people whose scores vary more. In our tests on films from 2019 onward, '
      + '8 out of 10 real next films landed inside a range built this way.')
  })

  test('an infinite half-life says all films count equally', () => {
    const text = explainText(F, { coverage: 0.8 }, null)
    expect(text).toContain('Based on 23 rated films. All films count equally. Their weighted average')
    expect(text).not.toContain('Recent films count more')
  })

  test('rounding: the two shares add up to 100, coverage to the nearest tenth, the half-life to whole years', () => {
    const text = explainText({ ...F, own_share: 0.825 }, { coverage: 0.86 }, 4.6)
    expect(text).toContain('we trust it 83% and the database average (6.3) 17%')
    expect(text).toContain('9 out of 10 real next films')
    expect(text).toContain('a film from 5 years before the latest counts half')
  })

  test('a real answer (Tom Hanks as an actor) reads as a sentence', () => {
    const { forecast } = hanksJson as CareerResponse
    const text = explainText({ ...forecast.explain!, mid: forecast.mid! }, forecast.test, forecast.explain!.half_life)
    expect(text).toContain('Based on 77 rated films. Recent films count more: a film from 5 years before the latest counts half.')
    expect(text).toContain('Their weighted average is 7.0; with this many films we trust it 91% and the database average (6.4) 9%, giving 6.9.')
    expect(text).toContain('8 out of 10 real next films')
  })
})
