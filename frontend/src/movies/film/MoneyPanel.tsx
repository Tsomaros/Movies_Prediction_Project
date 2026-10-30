// The film page's Money box: budget and box office as TMDB reports them, or in 2025 dollars.
import { useState } from 'react'

import type { MovieDetail as Film } from '@/api/client'
import { cn } from '@/lib/utils'
import { money } from '@/result/format'

export function MoneyPanel({ film }: { film: Film }) {
  const [inflated, setInflated] = useState(true)
  const m = film.money
  const rows = [
    { label: 'Budget', value: inflated ? m.budget_2025 : m.budget },
    { label: 'Worldwide box office', value: inflated ? m.revenue_2025 : m.revenue },
  ]
  return (
    <section aria-labelledby="money-heading" className="bg-card grid content-start gap-3 self-start rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="money-heading" className="font-semibold">Money</h2>
        <div role="radiogroup" aria-label="Show money" className="bg-muted inline-flex rounded-md p-0.5 text-xs">
          {[{ v: false, label: 'As reported' }, { v: true, label: 'In 2025 dollars' }].map(o => (
            <button key={o.label} type="button" role="radio" aria-checked={inflated === o.v} onClick={() => setInflated(o.v)}
              className={cn('rounded px-2 py-1', inflated === o.v ? 'bg-background shadow-xs' : 'text-muted-foreground')}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <dl className="grid gap-1 text-sm">
        {rows.map(r => (
          <div key={r.label} className="flex justify-between gap-4">
            <dt className="text-muted-foreground">{r.label}</dt>
            <dd className={r.value == null ? 'text-muted-foreground italic' : 'font-medium tabular-nums'}>
              {r.value == null ? 'not reported' : money(r.value)}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-muted-foreground text-xs">
        {inflated ? 'Adjusted to 2025 US dollars with the US consumer price index.' : `US dollars of ${film.year ?? 'the release year'}, as TMDB reports them.`}
      </p>
      {m.suspect && (
        <p className="rounded-md bg-amber-50 px-2 py-1 text-xs dark:bg-amber-950/30">
          Our cleaning rules doubt these figures{m.suspect_reason ? ` (${m.suspect_reason})` : ''}, so the models never learn from them.
        </p>
      )}
      {m.revenue_incomplete && (
        <p className="text-muted-foreground text-xs">Released less than six months before our data was pulled: the box office may still grow.</p>
      )}
    </section>
  )
}
