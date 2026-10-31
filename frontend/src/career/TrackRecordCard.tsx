// The track-record forecast of their next film (GET /people/{id}/career's `forecast`): the 80% range, its middle
// and "How is this calculated?", which opens the paragraph built from their own numbers and the role's backtest.
// Under the range sits the check line: what the forecast said from films up to 2025 and how later films scored
// (GET /people/{id}/career's `check`; absent without later films).
import { useState } from 'react'

import { Link } from 'react-router'

import type { CareerCheck, TrackForecast } from '@/api/client'
import { explainText, MOST_VOTED_NOTE } from '@/career/explain'
import { points } from '@/result/format'

/** "From films up to 2025 we said 6.6 – 8.3." and one sentence per later film, its title a link. */
function CheckLine({ check }: { check: CareerCheck }) {
  return (
    <p data-testid="career-check" className="text-muted-foreground text-sm">
      From films up to {check.up_to} we said {points(check.low)} – {points(check.high)}.
      {check.films.map(f => (
        <span key={f.movie_id}>
          {' '}<Link to={`/movies/${f.movie_id}`} className="text-primary underline">{f.title}</Link>
          {' '}scored {points(f.score)}{f.settling ? ' so far (still settling)' : ''}, {f.inside ? 'inside' : 'outside'}.
        </span>
      ))}
    </p>
  )
}

export function TrackRecordCard({ forecast, check }: { forecast: TrackForecast; check: CareerCheck | null }) {
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
      {check && <CheckLine check={check} />}
    </section>
  )
}
