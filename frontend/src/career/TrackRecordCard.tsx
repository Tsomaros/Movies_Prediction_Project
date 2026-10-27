// The track-record forecast of their next film (GET /people/{id}/career's `forecast`): the 80% range, its middle
// and "How is this calculated?", which opens the paragraph built from their own numbers and the role's backtest.
import { useState } from 'react'

import type { TrackForecast } from '@/api/client'
import { explainText, MOST_VOTED_NOTE } from '@/career/explain'
import { points } from '@/result/format'

export function TrackRecordCard({ forecast }: { forecast: TrackForecast }) {
  const [open, setOpen] = useState(false)
  const { low, mid, high, explain } = forecast
  const ok = forecast.status === 'ok' && low !== null && mid !== null && high !== null && explain !== null
  return (
    <section aria-labelledby="track-heading" className="bg-card grid content-start gap-2 rounded-lg border p-4">
      <h3 id="track-heading" className="text-sm font-medium">Their next film, from their track record</h3>
      {ok ? (
        <>
          <p className="text-3xl font-semibold tabular-nums">{points(low)} – {points(high)}</p>
          <p className="text-muted-foreground text-sm">Most likely around {points(mid)}</p>
          <button type="button" aria-expanded={open} onClick={() => setOpen(o => !o)}
            className="text-primary w-fit text-sm underline">How is this calculated?</button>
          {open && (
            <div className="grid gap-2 text-sm">
              <p>{explainText({ ...explain, mid }, forecast.test, explain.half_life)}</p>
              <p className="text-muted-foreground text-xs">{MOST_VOTED_NOTE}</p>
            </div>
          )}
        </>
      ) : (
        <p className="text-muted-foreground text-sm">Not enough rated films to forecast yet (needs 5)</p>
      )}
    </section>
  )
}
