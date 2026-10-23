// "Try a variation" until Day 13's compare page: after changing the form and predicting again, the results page
// shows what changed against the previous version (`?base=` in the URL) and how far each expected value moved.
import { Link } from 'react-router'

import type { Prediction, PredictForm } from '@/api/client'
import { changedFields } from '@/form/model'
import { factor, money, points, signedPoints } from '@/result/format'

export function VariationStrip({ base, next, basePrediction, prediction, withoutBase }: {
  base: PredictForm; next: PredictForm; basePrediction: Prediction | undefined; prediction: Prediction; withoutBase: string
}) {
  const changed = changedFields(base, next)
  return (
    <section aria-labelledby="variation-heading" data-testid="variation"
      className="border-primary/40 bg-accent/40 grid gap-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="variation-heading" className="font-semibold">Compared with your previous version</h2>
        <Link to={withoutBase} className="text-muted-foreground text-sm underline underline-offset-2 print:hidden">Hide</Link>
      </div>
      {changed.length === 0 ? (
        <p className="text-sm">Nothing has changed yet. Edit the inputs and predict again to see the difference.</p>
      ) : (
        <>
          <p className="text-sm">You changed the {changed.join(', ')}.</p>
          {basePrediction ? (
            <ul className="grid gap-1 text-sm sm:grid-cols-3">
              <li>Revenue: <strong className="tabular-nums">{factor(prediction.revenue.middle / basePrediction.revenue.middle)}</strong>{' '}
                <span className="text-muted-foreground">({money(basePrediction.revenue.middle)} → {money(prediction.revenue.middle)})</span></li>
              <li>Budget: <strong className="tabular-nums">{factor(prediction.budget.middle / basePrediction.budget.middle)}</strong>{' '}
                <span className="text-muted-foreground">({money(basePrediction.budget.middle)} → {money(prediction.budget.middle)})</span></li>
              <li>Score: <strong className="tabular-nums">{signedPoints(prediction.score.middle - basePrediction.score.middle)}</strong>{' '}
                <span className="text-muted-foreground">({points(basePrediction.score.middle)} → {points(prediction.score.middle)})</span></li>
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">Loading the previous version…</p>
          )}
          <p className="text-muted-foreground text-xs">
            These compare the expected values only; a change smaller than the ranges' width may not mean much.
          </p>
        </>
      )}
    </section>
  )
}
