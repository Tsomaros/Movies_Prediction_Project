// The Career section's chart (Day 14.8): a dot per dated film with a score, placed by release date, the career
// line (a rolling mean over rated films) and, when there is a forecast, a "Next film" column after the last year
// with the 80% band, its middle and a dashed step from the end of the line. "score" plots the score; "year" plots
// it minus the average of that year's rated films (0 is the middle line; the band moves by the newest year's
// average). Dots: lead roles filled, supporting hollow, crew filled, under 50 votes faint grey; the best film has
// a ring and a label. Hover shows a film's details and a click opens it; on touch the first tap shows them and a
// second tap on the same dot opens it. Colours are theme tokens, so both themes work; screen readers get one
// summary sentence (and the section's table).
import { memo, useEffect, useMemo, useRef, useState } from 'react'
import {
  ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, XAxis, YAxis,
} from 'recharts'

import type { CareerFilm, CareerResponse } from '@/api/client'
import { chartSummary } from '@/career/explain'
import { useMediaQuery } from '@/lib/useReducedMotion'
import { points, signedPoints } from '@/result/format'

export type CareerView = 'score' | 'year'
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

function kind(film: CareerFilm): Kind {
  if (!film.rated) return 'faint'
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
  const shift = (film: CareerFilm) => (view === 'year' ? film.year_avg : 0)
  const dots: Dot[] = data.films.flatMap(film => {
    const by = shift(film)
    if (film.score === null || by === null) return []
    return [{ x: position(film), y: film.score - by, film, kind: kind(film), best: film.movie_id === data.best_film?.movie_id }]
  })
  // line[i] belongs to the i-th rated film (both oldest first)
  const rated = data.films.filter(f => f.rated)
  const line = data.line.flatMap((p, i) => {
    const film = rated[i]
    const by = film ? shift(film) : null
    return film && by !== null ? [{ x: position(film), y: p.value - by }] : []
  })
  const lastYear = data.films.length ? data.films[data.films.length - 1].year : 0
  const next = lastYear + 1
  const f = data.forecast
  const bandShift = view === 'year' ? data.latest_year_avg : 0
  const band = f.status === 'ok' && f.low !== null && f.mid !== null && f.high !== null && bandShift !== null
    ? { low: f.low - bandShift, mid: f.mid - bandShift, high: f.high - bandShift } : null

  const ys = [...dots.map(d => d.y), ...line.map(p => p.y), ...(band ? [band.low, band.high] : []), ...(view === 'year' ? [0] : [])]
  const yDomain = [Math.floor(Math.min(...ys)), Math.ceil(Math.max(...ys))]
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
              Best: {points(film.score!)}
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
        <YAxis type="number" dataKey="y" domain={yDomain} allowDecimals={false} tick={AXIS} stroke="var(--border)"
          tickFormatter={v => (view === 'year' && v > 0 ? `+${v}` : String(v))} />
        {view === 'year' && <ReferenceLine y={0} className="career-zero" stroke="var(--muted-foreground)" strokeDasharray="2 3" />}
        {band && (
          <>
            <ReferenceArea x1={next - 0.5} x2={next + 0.5} fill="var(--muted)" fillOpacity={0.8}
              label={{ value: 'Next film', position: 'insideTop', fill: 'var(--muted-foreground)', fontSize: 11, dy: -18 }} />
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
  return (
    <div className="relative">
      <p className="sr-only">{chartSummary(data)}</p>
      <div aria-hidden>
        <Plot data={data} view={view} height={wide ? 260 : 220} events={events} />
      </div>
      {film && tip && (
        <div role="tooltip" className="bg-popover text-popover-foreground pointer-events-none absolute z-10 w-max max-w-56 -translate-x-1/2 rounded-md border px-2.5 py-1.5 text-xs shadow-md"
          style={{ left: tip.left, top: tip.top + 12 }}>
          <div className="font-medium">{film.title}</div>
          <div className="text-muted-foreground tabular-nums">
            {film.year}{film.score !== null && ` · ${points(film.score)}`}
            {view === 'year' && film.score !== null && film.year_avg !== null && ` (${signedPoints(film.score - film.year_avg)} vs its year)`}
          </div>
          {film.character && <div>as {film.character}</div>}
          {film.lead !== null && <div className="text-muted-foreground">{film.lead ? 'Lead role' : 'Supporting role'}</div>}
        </div>
      )}
    </div>
  )
}
