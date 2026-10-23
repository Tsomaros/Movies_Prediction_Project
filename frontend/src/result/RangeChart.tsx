// The ranges drawn to scale: budget and revenue on one shared log money axis (so "will it earn its budget back?"
// can be read off), with the break-even band (2–2.5× the budget) behind the revenue bar; the score on its own
// 0–10 axis. Plain positioned elements, so it reflows on a phone; screen readers get the same facts as a list.
import type { Prediction } from '@/api/client'
import { BREAK_EVEN, breakEven, money, moneyAxis, points } from '@/result/format'
import { cn } from '@/lib/utils'

type Range = { low: number; middle: number; high: number }

function Bar({ range, at, label, className }: { range: Range; at: (v: number) => number; label: string; className: string }) {
  const [left, right, mid] = [at(range.low), at(range.high), at(range.middle)]
  return (
    <>
      <div className={cn('absolute top-1/2 h-3 -translate-y-1/2 rounded-full', className)}
        style={{ left: `${left}%`, width: `${right - left}%` }} />
      <div className="bg-foreground ring-background absolute top-1/2 z-20 h-5 w-1 -translate-x-1/2 -translate-y-1/2 rounded-sm ring-2"
        style={{ left: `${mid}%` }} title={`${label}: expected`} />
    </>
  )
}

function Row({ label, sub, children }: { label: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[7rem_1fr] sm:items-center sm:gap-3">
      <div className="flex items-baseline justify-between gap-2 sm:block">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-muted-foreground text-xs tabular-nums">{sub}</div>
      </div>
      <div className="relative h-8">{children}</div>
    </div>
  )
}

function Ticks({ ticks, at, format }: { ticks: number[]; at: (v: number) => number; format: (v: number) => string }) {
  return (
    <div className="grid sm:grid-cols-[7rem_1fr] sm:gap-3">
      <div />
      <div className="text-muted-foreground relative h-5 text-xs tabular-nums">
        {ticks.map(t => (
          <span key={t} className="absolute -translate-x-1/2" style={{ left: `${at(t)}%` }}>{format(t)}</span>
        ))}
      </div>
    </div>
  )
}

function Grid({ ticks, at }: { ticks: number[]; at: (v: number) => number }) {
  return ticks.map(t => <div key={t} className="bg-border absolute inset-y-0 w-px" style={{ left: `${at(t)}%` }} />)
}

const BREAK_EVEN_WORDS = {
  below: 'below the break-even zone',
  within: 'inside the break-even zone',
  above: 'above the break-even zone',
}

export function RangeChart({ prediction }: { prediction: Prediction }) {
  const { budget, revenue, score } = prediction
  const base = revenue.budget_used
  const band = { low: BREAK_EVEN.low * base, high: BREAK_EVEN.high * base }
  const { at, ticks } = moneyAxis([budget.low, budget.high, revenue.low, revenue.high, band.high, base])
  const scoreAt = (v: number) => v * 10
  const where = breakEven(revenue.middle, base)
  const budgetWord = revenue.mode === 'given' ? 'your budget' : 'the estimated budget'

  return (
    <section aria-labelledby="chart-heading" className="bg-card grid gap-4 rounded-lg border p-4 sm:p-6">
      <div>
        <h2 id="chart-heading" className="text-lg font-semibold">The ranges side by side</h2>
        <p className="text-muted-foreground text-sm">
          Bars run from low to high; the upright mark is the expected value. Money is on a log scale: each step is ten
          times the last.
        </p>
      </div>

      <ul className="sr-only">
        <li>Budget: {money(budget.low)} to {money(budget.high)}, expected {money(budget.middle)}.</li>
        <li>Revenue: {money(revenue.low)} to {money(revenue.high)}, expected {money(revenue.middle)}.</li>
        <li>Break-even zone: {money(band.low)} to {money(band.high)}, 2 to 2.5 times {budgetWord}. The expected
          revenue is {BREAK_EVEN_WORDS[where]}.</li>
        <li>Audience score: {points(score.low)} to {points(score.high)} out of 10, expected {points(score.middle)}.</li>
      </ul>

      <div aria-hidden className="grid gap-2">
        <Row label="Budget" sub={budget.text}>
          <Grid ticks={ticks} at={at} />
          <Bar range={budget} at={at} label="Budget" className="bg-chart-2/70" />
          {budget.given != null && (
            <div className="border-foreground bg-background absolute top-1/2 z-20 size-3 -translate-x-1/2 -translate-y-1/2 rotate-45 border-2"
              style={{ left: `${at(budget.given)}%` }} title={`Your budget: ${money(budget.given)}`} />
          )}
        </Row>
        <Row label="Revenue" sub={revenue.text}>
          <Grid ticks={ticks} at={at} />
          <div data-testid="break-even-band"
            className="bg-[repeating-linear-gradient(135deg,var(--color-amber-500)_0_2px,transparent_2px_6px)] border-amber-600/70 absolute inset-y-0 z-10 border-x opacity-70"
            style={{ left: `${at(band.low)}%`, width: `${at(band.high) - at(band.low)}%` }} />
          <Bar range={revenue} at={at} label="Revenue" className="bg-primary/80" />
        </Row>
        <Ticks ticks={ticks} at={at} format={money} />
      </div>
      <p aria-hidden className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span><span className="bg-foreground mr-1.5 inline-block h-3 w-1 rounded-sm align-middle" />expected</span>
        {budget.given != null && (
          <span><span className="border-foreground mr-1.5 inline-block size-2.5 rotate-45 border-2 align-middle" />your budget</span>
        )}
      </p>

      <p className="text-sm" data-testid="break-even-text">
        <span className="mr-1 inline-block h-3 w-5 rounded-sm border border-amber-600/70 bg-[repeating-linear-gradient(135deg,var(--color-amber-500)_0_2px,transparent_2px_6px)] align-middle opacity-80" aria-hidden />
        <strong className="font-medium">Break-even zone</strong> ({money(band.low)}–{money(band.high)}): 2–2.5× {budgetWord}.
        The expected revenue is <strong className="font-medium">{BREAK_EVEN_WORDS[where]}</strong>.{' '}
        <span className="text-muted-foreground">
          A rule of thumb, not a forecast: cinemas keep about half the box office, and marketing comes on top of the budget.
        </span>
      </p>

      <div aria-hidden className="grid gap-2 border-t pt-4">
        <Row label="Audience score" sub={`${score.text} of 10`}>
          <Grid ticks={[0, 2, 4, 6, 8, 10]} at={scoreAt} />
          <Bar range={score} at={scoreAt} label="Audience score" className="bg-chart-4/80" />
        </Row>
        <Ticks ticks={[0, 2, 4, 6, 8, 10]} at={scoreAt} format={String} />
      </div>
    </section>
  )
}
