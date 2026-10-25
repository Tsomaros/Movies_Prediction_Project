// The person page's Career section (Day 14.8), for the role the page shows (acting, directing or writing; the
// page's own ?role= switch moves it): "Score" or "Revenue" in ?view= (score by default and then left out of the
// URL; an unknown value falls back to it), and everything follows the view: the chart of their films over the
// years with "View as table", the track-record forecast of their next film and the film model's two films. The
// model is asked only once /career says it can answer (one answer carries both metrics); writing has none. Loaded on demand with Recharts, so neither the main bundle nor the person page carries them.
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { ApiError, type CareerRole, type CareerView, type Recipe } from '@/api/client'
import { useCareer, useCareerModel, useMetaOptions } from '@/api/hooks'
import { CareerChart } from '@/career/CareerChart'
import { CareerTable } from '@/career/CareerTable'
import { ModelCard, type ModelKind } from '@/career/ModelCard'
import { TrackRecordCard } from '@/career/TrackRecordCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { encodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { cn } from '@/lib/utils'
import { recipeToForm } from '@/movies/predictLike'

const VIEWS: { value: CareerView; label: string }[] = [
  { value: 'score', label: 'Score' }, { value: 'revenue', label: 'Revenue' },
]
const readView = (value: string | null): CareerView => (value === 'revenue' ? 'revenue' : 'score')

function ViewToggle({ value, onChange }: { value: CareerView; onChange: (v: CareerView) => void }) {
  return (
    <div role="radiogroup" aria-label="Chart shows" className="bg-muted inline-flex rounded-md p-0.5">
      {VIEWS.map(v => (
        <button key={v.value} type="button" role="radio" aria-checked={value === v.value} onClick={() => onChange(v.value)}
          className={cn('h-8 rounded px-2.5 text-sm',
            value === v.value ? 'bg-background font-medium shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
          {v.label}
        </button>
      ))}
    </div>
  )
}

export default function CareerSection({ personId, name, role }: { personId: number; name: string; role: CareerRole }) {
  const [params, setParams] = useSearchParams()
  const view = readView(params.get('view'))
  const setView = (v: CareerView) => {
    const next = new URLSearchParams(params)
    if (v === 'score') next.delete('view')
    else next.set('view', v)
    setParams(next, { replace: true, preventScrollReset: true })
  }
  const navigate = useNavigate()
  const options = useMetaOptions()
  const [table, setTable] = useState(false)
  const [genre, setGenre] = useState<number | null>(null) // the chosen chip; null = the default pick

  const career = useCareer(personId, role)
  const modelOn = career.data?.model_available === true && role !== 'writing'
  const base = useCareerModel(personId, role, null, modelOn)
  const chip = useCareerModel(personId, role, genre, modelOn && genre !== null)

  const edit = (recipe: Recipe, kind: ModelKind) => {
    if (!options.data) return
    navigate(`/predict?${new URLSearchParams({
      [URL_PARAM]: encodeForm(recipeToForm(recipe, options.data)),
      [LIKE_PARAM]: kind === 'usual' ? `${name}'s usual film` : `Something new for ${name}`,
    })}`)
  }

  const data = career.data
  const charted = data !== undefined && data.films.length >= 2
  const noFilms = <p className="text-muted-foreground text-sm">Not enough dated films to chart a career</p>
  let body: React.ReactNode
  if (career.isError) {
    body = career.error instanceof ApiError && career.error.kind === 'not_found' ? noFilms : (
      <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
        <span>Couldn't load the career chart.</span>
        <Button variant="outline" size="sm" onClick={() => career.refetch()}>Retry</Button>
      </div>
    )
  } else if (!data) {
    body = <Skeleton data-testid="career-skeleton" className="h-[260px]" />
  } else {
    body = (
      <>
        {charted ? (
          <>
            <CareerChart key={view} data={data} view={view} onOpenMovie={id => navigate(`/movies/${id}`)} />
            <button type="button" aria-expanded={table} onClick={() => setTable(t => !t)}
              className="text-primary w-fit text-sm underline">View as table</button>
            {table && <CareerTable films={data.films} />}
          </>
        ) : noFilms}
        <div className="grid items-start gap-4 md:grid-cols-2">
          <TrackRecordCard forecast={data.metrics[view].forecast} view={view} />
          {role === 'writing' ? (
            <p className="text-muted-foreground text-sm">The film model has no writer input, so only the track record is shown.</p>
          ) : modelOn && (
            <ModelCard base={base} chip={chip} view={view} selected={genre} onChip={setGenre} onEdit={edit} canEdit={options.data !== undefined} />
          )}
        </div>
      </>
    )
  }

  return (
    <section aria-labelledby="career-heading" className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="career-heading" className="text-lg font-semibold">Career</h2>
        {charted && <ViewToggle value={view} onChange={setView} />}
      </div>
      {body}
    </section>
  )
}
