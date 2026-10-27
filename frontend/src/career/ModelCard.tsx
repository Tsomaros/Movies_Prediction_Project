// The score model on two made-up films (GET /people/{id}/career/model): "Their usual film" and "Something new",
// each with its range, the recipe in one line and "Edit in predictor"; genre chips under "Something new". The
// section owns the chosen chip and its queries: `chip` is the query for the chosen genre only (the default chip
// is the default answer, no request), and while a new chip loads the last numbers stay, faded.
import type { UseQueryResult } from '@tanstack/react-query'

import type { CareerModelResponse, Recipe } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { points } from '@/result/format'

export type ModelKind = 'usual' | 'new'
type Answer = UseQueryResult<CareerModelResponse>

const HONESTY = "The model doesn't know how they'd handle a new genre; it shows how films like this usually do with someone of their track record."

function recipeLine(r: Recipe): string {
  const people = r.labels.collaborators.length ? r.labels.collaborators.join(', ') : 'new collaborators'
  return [r.labels.genres.join(', '), r.labels.themes.join(', '), people, String(r.release_year)].filter(Boolean).join(' · ')
}

function Row({ title, film, onEdit, canEdit, testId, children }: {
  title: string; film: CareerModelResponse['new'] | NonNullable<CareerModelResponse['usual']>; onEdit: () => void
  canEdit: boolean; testId: string; children?: React.ReactNode
}) {
  const { low, high } = film.prediction
  return (
    <div className="grid gap-1">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h4 className="text-sm font-medium">{title}</h4>
        <span className="text-xl font-semibold tabular-nums">{points(low)} – {points(high)}</span>
      </div>
      <p className="text-muted-foreground text-sm" data-testid={testId}>{recipeLine(film.recipe)}</p>
      {children}
      <Button variant="outline" size="sm" className="w-fit" disabled={!canEdit} onClick={onEdit}>Edit in predictor</Button>
    </div>
  )
}

function Failed({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
      <span>Couldn't load the model forecast.</span>
      <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button>
    </div>
  )
}

export function ModelCard({ base, chip, selected, onChip, onEdit, canEdit }: {
  base: Answer; chip: Answer; selected: number | null; onChip: (genre: number | null) => void
  onEdit: (recipe: Recipe, kind: ModelKind) => void; canEdit: boolean
}) {
  const frame = (body: React.ReactNode) => (
    <section aria-labelledby="model-heading" className="bg-card grid content-start gap-4 rounded-lg border p-4">
      <h3 id="model-heading" className="text-sm font-medium">The film model</h3>
      {body}
    </section>
  )
  if (base.isError) return frame(<Failed onRetry={() => base.refetch()} />)
  if (!base.data?.usual) {
    return frame(
      <div data-testid="model-skeleton" aria-busy="true" className="grid gap-4">
        <span className="sr-only">Loading…</span>
        <Skeleton className="h-16" /><Skeleton className="h-16" />
      </div>,
    )
  }
  const { usual } = base.data
  const chips = base.data.chips ?? []
  const asked = selected !== null
  const faded = asked && (chip.isPlaceholderData || chip.isPending)
  const shown = (asked && chip.data?.new) || base.data.new
  // the chip whose numbers are on screen: a chip's recipe starts with its genre, and so does the default pick's
  const on = shown?.recipe.genres[0]

  return frame(
    <>
      <Row title="Their usual film" film={usual} testId="usual-recipe" canEdit={canEdit} onEdit={() => onEdit(usual.recipe, 'usual')} />
      {asked && chip.isError ? (
        <div className="grid gap-2">
          <h4 className="text-sm font-medium">Something new</h4>
          <Failed onRetry={() => chip.refetch()} />
        </div>
      ) : (
        <div aria-busy={faded} className={cn('transition-opacity', faded && 'opacity-50')}>
          <Row title="Something new" film={shown} testId="new-recipe" canEdit={canEdit && !faded} onEdit={() => onEdit(shown.recipe, 'new')}>
            {shown.note && <p className="text-muted-foreground text-xs">{shown.note}</p>}
            {chips.length > 0 && (
              <ul aria-label="Try a genre" className="flex flex-wrap gap-1.5 py-1">
                {chips.map(c => (
                  <li key={c.genre_id}>
                    <button type="button" aria-pressed={c.genre_id === on}
                      onClick={() => onChip(c.default ? null : c.genre_id)}
                      className={cn('rounded-full border px-2.5 py-0.5 text-xs',
                        c.genre_id === on ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted')}>
                      {c.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Row>
        </div>
      )}
      <p className="text-muted-foreground text-xs">{HONESTY}</p>
    </>,
  )
}
