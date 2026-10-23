// "Best release month": expected revenue and its likely range for each month of the planned year, on a log money
// axis. Your month is highlighted; months within the uncertainty of the best one are marked "about as good", so a
// small lead never reads as a clear winner. Screen readers get the same numbers as a table.
import type { ModelCard, SweepResponse } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { rankMonths } from '@/compare/sweep'
import { MONTHS } from '@/form/format'
import { cn } from '@/lib/utils'
import { money, moneyAxis } from '@/result/format'

const short = (m: number) => MONTHS[m - 1].slice(0, 3)

export function SweepLoading() {
  return (
    <div aria-busy="true" className="grid gap-2">
      <span className="sr-only">Trying all 12 months…</span>
      <Skeleton className="h-64 rounded-lg" />
    </div>
  )
}

export function SweepChart({ sweep, chosen, card, year }: {
  sweep: SweepResponse; chosen: number; card: ModelCard | undefined; year: number
}) {
  const points = sweep.points
  const mode = points[0]?.revenue_mode ?? 'given'
  const ratio = card ? (mode === 'estimated' ? card.uncertainty.revenue_estimated.ratio : card.uncertainty.revenue.ratio) : null
  const { best, aboutAsGood } = rankMonths(points, ratio)
  const { at, ticks } = moneyAxis(points.flatMap(p => [p.revenue.low, p.revenue.high]))
  const mine = points.find(p => p.value === chosen)
  const top = points.find(p => p.value === best)!
  const yours = !mine ? null : chosen === best ? 'is the best month for this film'
    : aboutAsGood.has(chosen) ? 'is about as good: the difference is within the uncertainty'
    : `expects ${money(mine.revenue.middle)}, ${Math.round((1 - mine.revenue.middle / top.revenue.middle) * 100)}% less than ${MONTHS[best - 1]}`

  return (
    <div className="grid gap-4">
      <p className="text-sm" data-testid="sweep-summary">
        Best: <strong>{MONTHS[best - 1]} {year}</strong> (expected {money(top.revenue.middle)}).{' '}
        {aboutAsGood.size === points.length - 1
          ? <>Every other month is about as good: for this film the release month makes little difference. </>
          : aboutAsGood.size > 0 && <>About as good: {[...aboutAsGood].map(m => MONTHS[m - 1]).join(', ')}. </>}
        {mine && <>Your month, {MONTHS[chosen - 1]}, {yours}.</>}
      </p>

      {/* sr-only on a wrapper: a table ignores its 1px width and would widen the page on a phone */}
      <div className="sr-only">
        <table>
          <caption>Expected box office by release month in {year}</caption>
          <thead><tr><th>Month</th><th>Expected</th><th>Likely range</th><th>Note</th></tr></thead>
          <tbody>
            {points.map(p => (
              <tr key={p.value}>
                <td>{MONTHS[p.value - 1]}</td><td>{money(p.revenue.middle)}</td><td>{p.revenue.text}</td>
                <td>{[p.value === best && 'best', aboutAsGood.has(p.value) && 'about as good', p.value === chosen && 'your month'].filter(Boolean).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div aria-hidden className="grid grid-cols-[3rem_1fr] gap-2" data-testid="sweep-chart">
        <div className="text-muted-foreground relative h-56 text-xs tabular-nums">
          {ticks.map(t => <span key={t} className="absolute right-0 translate-y-1/2" style={{ bottom: `${at(t)}%` }}>{money(t)}</span>)}
        </div>
        <div className="grid grid-cols-12 gap-0.5">
          {points.map(p => {
            const [low, high, mid] = [at(p.revenue.low), at(p.revenue.high), at(p.revenue.middle)]
            const isMine = p.value === chosen
            return (
              <div key={p.value} className="grid gap-1" data-testid={`month-${p.value}`}
                data-best={p.value === best || undefined} data-about={aboutAsGood.has(p.value) || undefined}>
                <div className={cn('relative h-56 rounded-sm', isMine && 'bg-primary/10 ring-primary/40 ring-1')}>
                  {ticks.map(t => <div key={t} className="bg-border absolute inset-x-0 h-px" style={{ bottom: `${at(t)}%` }} />)}
                  <div className={cn('absolute left-1/2 w-2 -translate-x-1/2 rounded-full',
                    isMine ? 'bg-primary/70' : p.value === best || aboutAsGood.has(p.value) ? 'bg-chart-2/80' : 'bg-muted-foreground/35')}
                    style={{ bottom: `${low}%`, height: `${high - low}%` }} />
                  <div className="bg-foreground ring-background absolute left-1/2 h-1 w-4 -translate-x-1/2 translate-y-1/2 rounded-sm ring-2"
                    style={{ bottom: `${mid}%` }} />
                </div>
                <div className={cn('text-center text-[11px] leading-tight', isMine ? 'text-foreground font-semibold' : 'text-muted-foreground')}>
                  {short(p.value)}
                  <div className="h-3 text-[10px]">{p.value === best ? '★' : aboutAsGood.has(p.value) ? '≈' : ''}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <p className="text-muted-foreground text-xs">
        Bars are the likely range (10th to 90th percentile), the mark is the expected value; log scale. ★ best month,
        ≈ about as good (within the uncertainty of the best); your month is shaded.
      </p>
    </div>
  )
}
