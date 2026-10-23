// The comparison: your film and each variant side by side (columns from `lg`, stacked on a phone), then their
// revenue ranges on one shared log money axis, each with its own break-even band. A change smaller than the
// uncertainty (the model card's threshold) is greyed out and says so, so a tiny shift never looks like news.
import { XIcon } from 'lucide-react'

import type { ModelCard, Prediction } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { driverChanges, meaningful, type Shift, type Target } from '@/compare/variants'
import { cn } from '@/lib/utils'
import { Bar, Grid, Row, Ticks } from '@/result/RangeChart'
import { BREAK_EVEN, factor, money, moneyAxis, signedPoints } from '@/result/format'

export type Column = {
  key: string
  title: string
  change: string | null // null for your film
  prediction: Prediction | undefined
  shift?: Record<Target, Shift>
  modeChanged?: boolean
  error?: string
  onRemove?: () => void
}

const TARGETS: { target: Target; label: string }[] = [
  { target: 'revenue', label: 'Box office' },
  { target: 'budget', label: 'Budget' },
  { target: 'score', label: 'Audience score' },
]

function ShiftText({ target, shift, card, mode }: { target: Target; shift: Shift; card: ModelCard | undefined; mode: 'given' | 'estimated' }) {
  const big = meaningful(target, shift, card, mode)
  const text = target === 'score' ? `${signedPoints(shift.points ?? 0)} points` : factor(shift.ratio ?? 1)
  return (
    <span data-testid={`shift-${target}`} data-meaningful={big === false ? 'no' : 'yes'}
      className={cn('text-xs tabular-nums', big === false ? 'text-muted-foreground' : 'font-semibold')}>
      {text}{big === false && ' · within the uncertainty'}
    </span>
  )
}

function VersionCard({ column, base, card }: { column: Column; base: Prediction | undefined; card: ModelCard | undefined }) {
  const p = column.prediction
  const moved = p && base && column.change ? driverChanges(base, p) : []
  return (
    <article data-testid="version" aria-label={column.title}
      className={cn('bg-card grid content-start gap-3 rounded-lg border p-4', column.change === null && 'border-primary/50')}>
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold">{column.title}</h3>
          {column.change !== column.title && <p className="text-muted-foreground text-sm">{column.change ?? 'As you planned it'}</p>}
        </div>
        {column.onRemove && (
          <Button variant="ghost" size="icon" className="-mt-1 -mr-2 size-8 print:hidden" onClick={column.onRemove}
            aria-label={`Remove ${column.title}`}>
            <XIcon />
          </Button>
        )}
      </header>
      {column.error ? (
        <p role="alert" className="text-destructive text-sm">{column.error}</p>
      ) : !p ? (
        <div className="grid gap-2" aria-busy="true"><Skeleton className="h-14" /><Skeleton className="h-14" /><Skeleton className="h-14" /></div>
      ) : (
        <>
          <dl className="grid gap-2">
            {TARGETS.map(({ target, label }) => (
              <div key={target} className="grid gap-0.5 border-t pt-2 first:border-t-0 first:pt-0">
                <dt className="text-muted-foreground text-xs">{label}</dt>
                <dd className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-xl font-semibold tabular-nums">{p[target].middle_text}</span>
                  <span className="text-muted-foreground text-xs tabular-nums">likely {p[target].text}</span>
                </dd>
                {column.shift && (
                  <dd><ShiftText target={target} shift={column.shift[target]} card={card} mode={base?.revenue.mode ?? 'given'} /></dd>
                )}
              </div>
            ))}
          </dl>
          {column.modeChanged && (
            <p className="text-muted-foreground text-xs">
              {p.revenue.mode === 'estimated' ? 'Revenue now uses the estimated budget.' : 'Revenue now uses the budget you gave.'}
            </p>
          )}
          {moved.length > 0 && (
            <div className="grid gap-1 border-t pt-2">
              <h4 className="text-xs font-medium">What moved (revenue)</h4>
              <ul className="text-muted-foreground grid gap-0.5 text-xs">{moved.map(m => <li key={m}>{m}</li>)}</ul>
            </div>
          )}
        </>
      )}
    </article>
  )
}

function RevenueChart({ columns }: { columns: Column[] }) {
  const ready = columns.filter((c): c is Column & { prediction: Prediction } => !!c.prediction && !c.error)
  if (ready.length < 2) return null
  const values = ready.flatMap(c => [c.prediction.revenue.low, c.prediction.revenue.high, BREAK_EVEN.high * c.prediction.revenue.budget_used])
  const { at, ticks } = moneyAxis(values)
  return (
    <section aria-labelledby="compare-chart-heading" className="bg-card grid gap-3 rounded-lg border p-4 sm:p-6">
      <div>
        <h2 id="compare-chart-heading" className="text-lg font-semibold">Box office side by side</h2>
        <p className="text-muted-foreground text-sm">
          One money axis for every version (log scale). The hatched band is each version's break-even zone, 2–2.5× its budget.
        </p>
      </div>
      <ul className="sr-only">
        {ready.map(c => (
          <li key={c.key}>{c.title}: {money(c.prediction.revenue.low)} to {money(c.prediction.revenue.high)}, expected {money(c.prediction.revenue.middle)}.</li>
        ))}
      </ul>
      <div aria-hidden className="grid gap-2">
        {ready.map(c => {
          const used = c.prediction.revenue.budget_used
          return (
            <Row key={c.key} label={c.title} sub={c.prediction.revenue.text}>
              <Grid ticks={ticks} at={at} />
              <div className="bg-[repeating-linear-gradient(135deg,var(--color-amber-500)_0_2px,transparent_2px_6px)] border-amber-600/70 absolute inset-y-1 z-10 border-x opacity-60"
                style={{ left: `${at(BREAK_EVEN.low * used)}%`, width: `${at(BREAK_EVEN.high * used) - at(BREAK_EVEN.low * used)}%` }} />
              <Bar range={c.prediction.revenue} at={at} label={c.title} className={c.change === null ? 'bg-primary/80' : 'bg-chart-2/70'} />
            </Row>
          )
        })}
        <Ticks ticks={ticks} at={at} format={money} />
      </div>
    </section>
  )
}

export function CompareView({ columns, card }: { columns: Column[]; card: ModelCard | undefined }) {
  const base = columns[0]?.prediction
  return (
    <div className="grid gap-6">
      <div className={cn('grid gap-4', columns.length > 1 && 'md:grid-cols-2', columns.length > 2 && 'lg:grid-cols-4')}>
        {columns.map(c => <VersionCard key={c.key} column={c} base={base} card={card} />)}
      </div>
      {card && columns.length > 1 && (
        <p className="text-muted-foreground text-xs" data-testid="threshold-note">
          Greyed changes are within the uncertainty: smaller than a tenth of a typical range ({factor(card.uncertainty.revenue.ratio)} for
          box office, {factor(card.uncertainty.budget.ratio)} for budget, {card.uncertainty.score.points.toFixed(2)} points for the
          score), measured on films from {card.uncertainty.years}.
        </p>
      )}
      <RevenueChart columns={columns} />
    </div>
  )
}
