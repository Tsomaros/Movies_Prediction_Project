// The answer first: three cards (revenue, budget, audience score), each with the expected value, the range and
// the badges that say where to be careful: "Rough estimate" (an unusually wide range), "Budget estimated"
// (revenue without a budget from the form) and the given budget against what similar films cost.
import type { ReactNode } from 'react'

import type { Prediction } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { money } from '@/result/format'

const POSITION_BADGE = {
  below: 'Budget below similar films',
  'at the low end': 'Budget at the low end',
  within: 'Budget typical for similar films',
  'at the high end': 'Budget at the high end',
  above: 'Budget above similar films',
} as const

function Card({ title, value, range, children, testId }: {
  title: string; value: string; range: string; children?: ReactNode; testId: string
}) {
  return (
    <article data-testid={testId} className="bg-card grid content-start gap-2 rounded-lg border p-4 shadow-xs">
      <h2 className="text-muted-foreground text-sm font-medium">{title}</h2>
      <p className="text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="text-sm">Likely <span className="font-medium tabular-nums">{range}</span></p>
      {children}
    </article>
  )
}

function Rough() {
  return (
    <>
      <Badge variant="outline" className="border-amber-600/60 text-amber-800 dark:text-amber-300">Rough estimate</Badge>
      <p className="text-muted-foreground text-xs">Films like this vary a lot, so the range is unusually wide.</p>
    </>
  )
}

export function Summary({ prediction }: { prediction: Prediction }) {
  const { revenue, budget, score } = prediction
  const comparison = budget.comparison
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Card testId="card-revenue" title="Box office, worldwide" value={revenue.middle_text} range={revenue.text}>
        <div className="flex flex-wrap gap-1">
          {revenue.mode === 'estimated' && <Badge variant="secondary">Budget estimated</Badge>}
        </div>
        {revenue.mode === 'estimated' && (
          <p className="text-muted-foreground text-xs">
            No budget given, so this uses the estimated budget of {money(revenue.budget_used)}.
          </p>
        )}
        {revenue.rough && <Rough />}
      </Card>
      <Card testId="card-budget" title={budget.given != null ? 'Budget for films like this' : 'Estimated budget'}
        value={budget.middle_text} range={budget.text}>
        {comparison.position && (
          <>
            <Badge variant="secondary">{POSITION_BADGE[comparison.position]}</Badge>
            <p className="text-muted-foreground text-xs">{comparison.sentence}.</p>
          </>
        )}
        {budget.rough && <Rough />}
      </Card>
      <Card testId="card-score" title="Audience score (TMDB, of 10)" value={score.middle_text} range={score.text} />
    </div>
  )
}
