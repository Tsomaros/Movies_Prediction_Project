// The honest part of the results page: the warnings for this form (new people, big budget, empty fields…), the
// limitations that always apply, and "How accurate is this?" with the served models' own test numbers from
// GET /model-card, so the panel can never disagree with the deployed models.
import { AlertTriangleIcon, InfoIcon } from 'lucide-react'

import type { ModelCard, Prediction } from '@/api/client'
import { useModelCard } from '@/api/hooks'
import { Skeleton } from '@/components/ui/skeleton'
import { factor, percent } from '@/result/format'

export const README_URL = 'https://github.com/Tsomaros/Movies_Prediction_Project#readme'

export function Warnings({ prediction }: { prediction: Prediction }) {
  const notes = [...prediction.warnings.map(w => ({ key: w.code, text: w.text })), { key: 'score', text: prediction.score.note }]
  return (
    <section aria-labelledby="notes-heading" className="grid gap-2">
      <h2 id="notes-heading" className="text-lg font-semibold">Notes on this prediction</h2>
      <ul className="grid gap-2">
        {notes.map(n => (
          <li key={n.key} data-testid={`note-${n.key}`}
            className="flex gap-2 rounded-md border border-amber-600/40 bg-amber-50 px-3 py-2 text-sm dark:bg-amber-950/30">
            <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-amber-700 dark:text-amber-400" aria-hidden />
            {n.text}
          </li>
        ))}
      </ul>
    </section>
  )
}

export function Limitations() {
  return (
    <aside aria-label="Limitations" data-testid="limitations" className="bg-muted/60 flex gap-2 rounded-md px-3 py-3 text-sm">
      <InfoIcon className="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden />
      <p>
        <strong className="font-medium">Estimates, not guarantees.</strong> These ranges come from patterns in past
        films: about 8 times in 10 the real figure lands inside them. They can't know the script, the marketing or what
        else opens that weekend. Money is in 2025 US dollars, revenue is worldwide box office, and budgets leave out
        marketing.
      </p>
    </aside>
  )
}

type Targets = ModelCard['test']['targets']

const ROWS = (revenue: 'revenue' | 'revenue_estimated') => [
  { key: revenue, label: revenue === 'revenue' ? 'Revenue' : 'Revenue (budget estimated)' },
  { key: 'budget', label: 'Budget' },
  { key: 'score', label: 'Audience score' },
] as const

function miss(m: Targets['score']['model']) {
  return m.typical_factor != null ? `off by ${factor(m.typical_factor)}` : `off by ${m.mae!.toFixed(1)} points`
}

function AccuracyTable({ caption, targets, revenue }: {
  caption: string; targets: Targets; revenue: 'revenue' | 'revenue_estimated'
}) {
  return (
    <table className="w-full text-left text-sm">
      <caption className="mb-1 text-left font-medium">{caption}</caption>
      <thead className="text-muted-foreground text-xs">
        <tr>
          <th scope="col" className="py-1 pr-2 font-normal">Estimate</th>
          <th scope="col" className="py-1 pr-2 font-normal">Real figure in range</th>
          <th scope="col" className="py-1 font-normal">Expected value typically… (simple rule)</th>
        </tr>
      </thead>
      <tbody>
        {ROWS(revenue).map(({ key, label }) => {
          const t = targets[key]
          return (
            <tr key={key} className="border-t">
              <th scope="row" className="py-1.5 pr-2 font-normal">{label}</th>
              <td className="py-1.5 pr-2 tabular-nums">{percent(t.model.coverage)} <span className="text-muted-foreground">of {t.films.toLocaleString('en-US')}</span></td>
              <td className="py-1.5 tabular-nums">{miss(t.model)} <span className="text-muted-foreground">({miss(t.baseline).replace('off by ', '')})</span></td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export function Accuracy({ mode }: { mode: Prediction['revenue']['mode'] }) {
  const card = useModelCard()
  const revenue = mode === 'given' ? 'revenue' : 'revenue_estimated'
  return (
    <section aria-labelledby="accuracy-heading" className="bg-card grid gap-3 rounded-lg border p-4 sm:p-6">
      <h2 id="accuracy-heading" className="text-lg font-semibold">How accurate is this?</h2>
      {card.isPending && <Skeleton className="h-40 w-full" />}
      {card.isError && <p className="text-muted-foreground text-sm">The accuracy numbers couldn't load right now.</p>}
      {card.data && (
        <div className="grid gap-4" data-testid="accuracy">
          <p className="text-sm">
            The ranges aim to hold the real figure {percent(card.data.coverage_target)} of the time. Here is how they
            did on films the models had never seen, next to the best simple rule we compared against.
          </p>
          <AccuracyTable caption={`Films released ${card.data.test.years}, tested once (${card.data.test.run_at})`}
            targets={card.data.test.targets} revenue={revenue} />
          <AccuracyTable caption={`Films released in ${card.data.holdout.years}, after the training data ends`}
            targets={card.data.holdout.targets} revenue={revenue} />
          <p className="text-muted-foreground text-sm">
            Scores of 2026 films land in range less often: a new film's TMDB score usually starts high and settles in
            its first year, and the models predict the settled score. Models version {card.data.model_version}, built
            from {card.data.data.films.toLocaleString('en-US')} films released {card.data.data.first_year}–{card.data.data.last_year}.{' '}
            <a href={README_URL} target="_blank" rel="noreferrer" className="text-primary underline underline-offset-2">
              Read how it was tested
            </a>
          </p>
        </div>
      )}
    </section>
  )
}
