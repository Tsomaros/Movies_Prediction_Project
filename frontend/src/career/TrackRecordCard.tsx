// The track-record forecast of their next film for the section's view (GET /people/{id}/career's
// `metrics.score.forecast` or `metrics.revenue.forecast`): the 80% range (points, or money() in 2025 $), its middle
// and "How is this calculated?", which opens the paragraph built from their own numbers and the role's backtest.
// Revenue adds one plain line under the range from the backtest: how rarely a next film lands within 2× of the
// middle, so the wide range reads as honest rather than broken.
import { useState } from 'react'

import type { CareerView, TrackForecast } from '@/api/client'
import { explainText, hardToCall, NOTES } from '@/career/explain'
import { money, points } from '@/result/format'

const NOT_ENOUGH: Record<CareerView, string> = {
  score: 'Not enough rated films to forecast yet (needs 5)',
  revenue: 'Not enough films with a known box office to forecast yet (needs 5)',
}

export function TrackRecordCard({ forecast, view }: { forecast: TrackForecast; view: CareerView }) {
  const [open, setOpen] = useState(false)
  const { low, mid, high, explain } = forecast
  const ok = forecast.status === 'ok' && low !== null && mid !== null && high !== null && explain !== null
  const show = view === 'score' ? points : money
  const hard = view === 'revenue' ? hardToCall(forecast.test) : null
  return (
    <section aria-labelledby="track-heading" className="bg-card grid content-start gap-2 rounded-lg border p-4">
      <h3 id="track-heading" className="text-sm font-medium">Their next film, from their track record</h3>
      {ok ? (
        <>
          <p className="text-3xl font-semibold tabular-nums">{show(low)} – {show(high)}</p>
          <p className="text-muted-foreground text-sm">Most likely around {show(mid)}</p>
          {hard && <p className="text-muted-foreground text-xs">{hard}</p>}
          <button type="button" aria-expanded={open} onClick={() => setOpen(o => !o)}
            className="text-primary w-fit text-sm underline">How is this calculated?</button>
          {open && (
            <div className="grid gap-2 text-sm">
              <p>{explainText({ ...explain, mid }, forecast.test, explain.half_life, view)}</p>
              <p className="text-muted-foreground text-xs">{NOTES[view]}</p>
            </div>
          )}
        </>
      ) : (
        <p className="text-muted-foreground text-sm">{NOT_ENOUGH[view]}</p>
      )}
    </section>
  )
}
