import { describe, expect, test } from 'vitest'

import type { CareerResponse } from '@/api/client'
import { chartSummary, explainText, hardToCall } from '@/career/explain'
import hanksJson from '@/test/career_hanks.json'

const F = { n_films: 23, own_avg: 6.9, own_share: 0.82, db_avg: 6.3, mid: 6.8 }
const HANKS = hanksJson as CareerResponse

describe('the "How is this calculated?" paragraph', () => {
  test("uses the person's numbers and the backtest hit rate, exactly as the spec words it", () => {
    expect(explainText(F, { coverage: 0.81 }, 8, 'score')).toBe(
      'Based on 23 rated films. Recent films count more: a film from 8 years before the latest counts half. '
      + 'Their weighted average is 6.9; with this many films we trust it 82% and the database average (6.3) 18%, '
      + 'giving 6.8. The range is wider for people whose scores vary more. In our tests on films from 2019 onward, '
      + '8 out of 10 real next films landed inside a range built this way.')
  })

  test('an infinite half-life says all films count equally', () => {
    const text = explainText(F, { coverage: 0.8 }, null, 'score')
    expect(text).toContain('Based on 23 rated films. All films count equally. Their weighted average')
    expect(text).not.toContain('Recent films count more')
  })

  test('rounding: the two shares add up to 100, coverage to the nearest tenth, the half-life to whole years', () => {
    const text = explainText({ ...F, own_share: 0.825 }, { coverage: 0.86 }, 4.6, 'score')
    expect(text).toContain('we trust it 83% and the database average (6.3) 17%')
    expect(text).toContain('9 out of 10 real next films')
    expect(text).toContain('a film from 5 years before the latest counts half')
  })

  test('a real answer (Tom Hanks as an actor) reads as a sentence', () => {
    const { forecast } = HANKS.metrics.score
    const text = explainText({ ...forecast.explain!, mid: forecast.mid! }, forecast.test, forecast.explain!.half_life, 'score')
    expect(text).toContain('Based on 77 rated films. Recent films count more: a film from 5 years before the latest counts half.')
    expect(text).toContain('Their weighted average is 7.0; with this many films we trust it 91% and the database average (6.4) 9%, giving 6.9.')
    expect(text).toContain('8 out of 10 real next films')
  })

  test('revenue: the typical box office in 2025 dollars, with money() and the same weights rule', () => {
    const { forecast } = HANKS.metrics.revenue
    expect(explainText({ ...forecast.explain!, mid: forecast.mid! }, forecast.test, forecast.explain!.half_life, 'revenue')).toBe(
      'Based on 58 films with a trusted box office (in 2025 dollars). Recent films count more: a film from 12 years '
      + 'before the latest counts half. Their typical box office is $120M; with this many films we trust it 93% and '
      + "the database's typical film ($5.5M) 7%, giving $95M. The range is wider for people whose results vary more. "
      + 'In our tests on films from 2019 onward, 8 out of 10 real next films landed inside a range built this way.')
    expect(explainText({ ...F, n_films: 1, own_avg: 2e7, db_avg: 5e6, mid: 9e6 }, { coverage: 0.8 }, null, 'revenue'))
      .toContain('Based on 1 film with a trusted box office (in 2025 dollars). All films count equally. Their typical box office is $20M')
  })
})

describe('the revenue line under the range', () => {
  test('says how rarely a next film lands within 2× of the middle, from the backtest numbers', () => {
    expect(hardToCall(HANKS.metrics.revenue.forecast.test)).toBe(
      'Box office is hard to call: in our tests only 23% of real next films landed within 2× of the middle, though 85% fell inside the range.')
    expect(hardToCall({ coverage: 0.5, n_people: 10, within_2x: 0.404 })).toContain('only 40% of real next films')
  })

  test('the score has none', () => {
    expect(hardToCall(HANKS.metrics.score.forecast.test)).toBeNull()
  })
})

describe('the chart summary for screen readers', () => {
  test('one sentence per view', () => {
    expect(chartSummary(HANKS, 'score')).toBe('77 rated films from 1980 to 2025; average 6.8; best film The Green Mile')
    expect(chartSummary(HANKS, 'revenue')).toMatch(/^58 films with a known box office from \d{4} to \d{4}; typical \$[\d.]+[MB]; best film Toy Story 3$/)
  })
})
