// Numbers on the results page: never more precision than the models have.
//
//   money(n)            -> two significant figures with K / M / B, like the API's own texts: 1580690000 -> "$1.6B"
//   points(n)           -> a score with one decimal: 7.357 -> "7.4"
//   percent(share)      -> 0.7737 -> "77%"
//   factor(ratio)       -> a money change as a factor: 1.3 -> "×1.3", 0.5 -> "×0.5"
//   signedPoints(d)     -> a score change: 0.24 -> "+0.2", -0.05 -> "0.0"
//   BREAK_EVEN          -> the break-even rule of thumb: revenue of 2 to 2.5 times the budget
//   breakEven(revenue, budget) -> where the expected revenue sits against that band
//   moneyAxis(values)   -> a log axis over the values: at(v) in percent of the width, and its ticks

/** Mirrors ml/models/chain.py format_money, so the page's numbers read like the API's texts. */
export function money(dollars: number): string {
  const value = Number(dollars.toPrecision(2))
  for (const [size, suffix] of [[1e9, 'B'], [1e6, 'M'], [1e3, 'K']] as const) {
    if (value >= size) return `$${+(value / size).toPrecision(2)}${suffix}`
  }
  return `$${value}`
}

export const points = (score: number) => score.toFixed(1)
export const percent = (share: number) => `${Math.round(share * 100)}%`
export const factor = (ratio: number) => `×${ratio >= 10 ? Math.round(ratio) : +ratio.toPrecision(2)}`

export function signedPoints(diff: number) {
  const text = Math.abs(diff).toFixed(1)
  return text === '0.0' ? '0.0' : `${diff > 0 ? '+' : '−'}${text}`
}

/** Cinemas keep about half of the box office, and marketing often costs a large share of the budget, so a film
 *  usually needs worldwide revenue of about 2 to 2.5 times its budget to make money. A rule of thumb only. */
export const BREAK_EVEN = { low: 2, high: 2.5 } as const

export type BreakEven = 'below' | 'within' | 'above'

export function breakEven(revenue: number, budget: number): BreakEven {
  if (revenue < BREAK_EVEN.low * budget) return 'below'
  return revenue > BREAK_EVEN.high * budget ? 'above' : 'within'
}

/** A log axis padded around every value it must show, with ticks at 1, 10, 100… (and 3, 30… when few fit). */
export function moneyAxis(values: number[]) {
  const lo = Math.log10(Math.min(...values) / 1.6)
  const hi = Math.log10(Math.max(...values) * 1.6)
  const at = (v: number) => ((Math.log10(v) - lo) / (hi - lo)) * 100
  const ticks: number[] = []
  for (let p = Math.ceil(lo); p <= Math.floor(hi); p++) ticks.push(10 ** p)
  if (ticks.length < 3) {
    for (let p = Math.floor(lo); p <= Math.ceil(hi); p++) {
      const three = 3 * 10 ** p
      if (Math.log10(three) > lo && Math.log10(three) < hi) ticks.push(three)
    }
    ticks.sort((a, b) => a - b)
  }
  return { at, ticks }
}
