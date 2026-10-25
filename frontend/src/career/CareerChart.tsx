// The Career section's chart (Day 14.8) for the section's view: a dot per dated film with a value, placed by
// release date, the career line (a rolling mean over films with a value) and, when there is a forecast, a "Next
// film" column after the last year with the 80% band, its middle and a dashed step from the end of the line.
// "score" plots the score (dots: lead roles filled, supporting hollow, crew filled, under 50 votes faint grey);
// "revenue" plots the trusted box office in 2025 $ on a log axis with money() ticks at powers of 10 (only films
// with a box office, no faint dots). The best film has a ring and a label. Everything comes from
// `metrics[view]`. Hover shows a film's details and a click opens it; on touch the first tap shows them and a
// second tap on the same dot opens it. Colours are theme tokens, so both themes work; screen readers get one
// summary sentence (and the section's table).
import { memo, useEffect, useMemo, useRef, useState } from 'react'
import {
  ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, XAxis, YAxis,
} from 'recharts'

import type { CareerFilm, CareerResponse, CareerView } from '@/api/client'
import { chartSummary } from '@/career/explain'
import { useMediaQuery } from '@/lib/useReducedMotion'
import { money, moneyAxis, points } from '@/result/format'

type Kind = 'lead' | 'support' | 'crew' | 'faint'
type Dot = { x: number; y: number; film: CareerFilm; kind: Kind; best: boolean }
type Tip = { film: CareerFilm; left: number; top: number }

const AXIS = { fill: 'var(--muted-foreground)', fontSize: 12 }

/** A film's place on the year axis: its release date as a fraction of the year (mid-year without a date), so
 *  several films of one year sit side by side in release order. */
function position(film: CareerFilm): number {
  const m = film.release_date?.match(/^\d{4}-(\d{2})-(\d{2})$/)
  if (!m) return film.year + 0.5
  return film.year + (Number(m[1]) - 1 + (Number(m[2]) - 1) / 31) / 12
}

/** The film's value in a view: its score (rated or not), or its trusted box office. */
const value = (film: CareerFilm, view: CareerView) => (view === 'score' ? film.score : film.revenue)

function kind(film: CareerFilm, view: CareerView): Kind {
  if (view === 'score' && !film.rated) return 'faint'
  return film.lead === null ? 'crew' : film.lead ? 'lead' : 'support'
}

type Events = {
  show: (film: CareerFilm, left: number, top: number) => void
  hide: () => void
  click: (film: CareerFilm, left: number, top: number) => void
  pointer: (type: string) => void
}

/** The chart itself, memoised: hovering only changes the tooltip, and re-rendering the chart then would remount
 *  every dot under the pointer. */
const Plot = memo(function Plot({ data, view, height, events }:
  { data: CareerResponse; view: CareerView; height: number; events: Events }) {
  const metric = data.metrics[view]
  const dots: Dot[] = data.films.flatMap(film => {
    const y = value(film, view)
    return y === null ? [] : [{ x: position(film), y, film, kind: kind(film, view), best: film.movie_id === metric.best_film?.movie_id }]
  })
  // line[i] belongs to the i-th film that counts for the line (both oldest first): rated films for the score,
  // films with a box office for the revenue
  const counted = data.films.filter(f => (view === 'score' ? f.rated : f.revenue !== null))
  const line = metric.line.flatMap((p, i) => (counted[i] ? [{ x: position(counted[i]), y: p.value }] : []))
  const lastYear = data.films.length ? data.films[data.films.length - 1].year : 0
  const next = lastYear + 1
  const f = metric.forecast
  const band = f.status === 'ok' && f.low !== null && f.mid !== null && f.high !== null
    ? { low: f.low, mid: f.mid, high: f.high } : null

  const ys = [...dots.map(d => d.y), ...line.map(p => p.y), ...(band ? [band.low, band.high] : [])]
  // revenue: a log axis padded like the other money charts, ticks at 1, 10, 100… ($1M, $10M…)
  const log = view === 'revenue'
  const yDomain = log
    ? [Math.min(...ys) / 1.6, Math.max(...ys) * 1.6]
    : [Math.floor(Math.min(...ys)), Math.ceil(Math.max(...ys))]
  const yTicks = log ? moneyAxis(ys).ticks : undefined
  const firstYear = data.films.length ? data.films[0].year : 0
  const xDomain = [firstYear, band ? next + 0.5 : lastYear + 1]

  const renderDot = (props: unknown) => {
    const { cx = 0, cy = 0, payload } = props as { cx?: number; cy?: number; payload: Dot }
    const { film, best } = payload
    const style = {
      lead: { fill: 'var(--primary)', stroke: 'var(--primary)' },
      crew: { fill: 'var(--primary)', stroke: 'var(--primary)' },
      support: { fill: 'var(--background)', stroke: 'var(--primary)' },
      faint: { fill: 'var(--muted-foreground)', stroke: 'none', opacity: 0.35 },
    }[payload.kind]
    return (
      <g data-testid={`dot-${payload.kind}`} style={{ cursor: 'pointer' }}
        onPointerDown={e => events.pointer(e.pointerType)}
        onPointerEnter={e => { if (e.pointerType === 'mouse') events.show(film, cx, cy) }}
        onPointerLeave={e => { if (e.pointerType === 'mouse') events.hide() }}
        onClick={() => events.click(film, cx, cy)}>
        <circle cx={cx} cy={cy} r={10} fill="transparent" />
        <circle cx={cx} cy={cy} r={4} strokeWidth={1.5} {...style} />
        {best && (
          <g data-testid="best-marker">
            <circle cx={cx} cy={cy} r={8} fill="none" stroke="var(--foreground)" strokeWidth={1.5} />
            <text x={cx} y={cy - 12} textAnchor="middle" fontSize={11} fill="var(--foreground)">
              Best: {log ? money(value(film, view)!) : points(film.score!)}
            </text>
          </g>
        )}
      </g>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart margin={{ top: 20, right: 12, bottom: 0, left: -16 }}>
        <XAxis type="number" dataKey="x" domain={xDomain} allowDecimals={false} tick={AXIS}
          stroke="var(--border)" tickFormatter={v => String(Math.floor(v))} />
        {log ? (
          <YAxis type="number" dataKey="y" scale="log" domain={yDomain} ticks={yTicks} tick={AXIS}
            stroke="var(--border)" tickFormatter={v => money(v)} />
        ) : (
          <YAxis type="number" dataKey="y" domain={yDomain} allowDecimals={false} tick={AXIS} stroke="var(--border)" />
        )}
        {band && (
          <>
            <ReferenceArea x1={next - 0.5} x2={next + 0.5} fill="var(--muted)" fillOpacity={0.8}
              label={{ value: 'Next film', position: 'insideTopRight', fill: 'var(--muted-foreground)', fontSize: 11, dy: -18 }} />
            <ReferenceArea x1={next - 0.3} x2={next + 0.3} y1={band.low} y2={band.high}
              shape={(p: { x?: number; y?: number; width?: number; height?: number }) => (
                <rect data-testid="forecast-band" x={p.x} y={p.y} width={p.width} height={p.height} rx={3}
                  fill="var(--primary)" fillOpacity={0.25} />
              )} />
            <ReferenceLine segment={[{ x: next - 0.3, y: band.mid }, { x: next + 0.3, y: band.mid }]}
              stroke="var(--primary)" strokeWidth={2} />
          </>
        )}
        <Line data={line} dataKey="y" type="monotone" stroke="var(--primary)" strokeWidth={2} dot={false}
          isAnimationActive={false} />
        {band && line.length > 0 && (
          <Line data={[line[line.length - 1], { x: next, y: band.mid }]} dataKey="y" stroke="var(--primary)"
            strokeWidth={1.5} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
        )}
        <Scatter data={dots} dataKey="y" shape={renderDot} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
})

export function CareerChart({ data, view, onOpenMovie }:
  { data: CareerResponse; view: CareerView; onOpenMovie: (id: number) => void }) {
  const wide = useMediaQuery('(min-width: 640px)')
  const [tip, setTip] = useState<Tip | null>(null)
  const pointer = useRef('mouse')
  const shown = useRef<number | null>(null) // the film in the tooltip, for the second tap
  const open = useRef(onOpenMovie)
  useEffect(() => { open.current = onOpenMovie })

  const events = useMemo<Events>(() => {
    const show = (film: CareerFilm, left: number, top: number) => { shown.current = film.movie_id; setTip({ film, left, top }) }
    const hide = () => { shown.current = null; setTip(null) }
    return {
      show, hide,
      pointer: type => { pointer.current = type },
      click: (film, left, top) => {
        if (pointer.current === 'touch' && shown.current !== film.movie_id) show(film, left, top)
        else open.current(film.movie_id)
      },
    }
  }, [])

  const film = tip?.film
  if (!data.films.some(f => value(f, view) !== null)) {
    return <p className="text-muted-foreground text-sm">{view === 'score' ? 'No films with a score to chart' : 'No films with a known box office to chart'}</p>
  }
  return (
    <div className="relative">
      <p className="sr-only">{chartSummary(data, view)}</p>
      <div aria-hidden>
        <Plot data={data} view={view} height={wide ? 260 : 220} events={events} />
      </div>
      {film && tip && (
        <div role="tooltip" className="bg-popover text-popover-foreground pointer-events-none absolute z-10 w-max max-w-56 -translate-x-1/2 rounded-md border px-2.5 py-1.5 text-xs shadow-md"
          style={{ left: tip.left, top: tip.top + 12 }}>
          <div className="font-medium">{film.title}</div>
          <div className="text-muted-foreground tabular-nums">
            {film.year}
            {view === 'score' && film.score !== null && ` · ${points(film.score)}`}
            {view === 'revenue' && film.revenue !== null && ` · ${money(film.revenue)} box office`}
          </div>
          {film.character && <div>as {film.character}</div>}
          {film.lead !== null && <div className="text-muted-foreground">{film.lead ? 'Lead role' : 'Supporting role'}</div>}
        </div>
      )}
    </div>
  )
}
