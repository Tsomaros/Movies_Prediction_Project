// /predict/result: the results page. The form travels in the URL (?f=, as on the form page), so a result can be
// shared, refreshed or printed; `?base=` adds the previous version for "Try a variation".
//
// Order: the answer (summary cards) -> the ranges to scale with the break-even band -> why (drivers) -> films like
// it -> notes, limitations and accuracy -> actions. The prediction comes from the query cache when the form page
// just asked for it, else from one request; while it loads, skeletons keep the layout still.
import { LinkIcon, PencilIcon, PrinterIcon, ShuffleIcon } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { ApiError, type PredictForm } from '@/api/client'
import { RATE_LIMITED } from '@/api/errors'
import { usePrediction } from '@/api/hooks'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { MONTHS } from '@/form/format'
import { toApiBody, type FormValues } from '@/form/model'
import { BASE_PARAM, decodeForm, URL_PARAM } from '@/form/persist'
import PageHeading from '@/pages/PageHeading'
import { Comparables } from '@/result/Comparables'
import { Drivers } from '@/result/Drivers'
import { Accuracy, Limitations, Warnings } from '@/result/Notes'
import { RangeChart } from '@/result/RangeChart'
import { Summary } from '@/result/Summary'
import { VariationStrip } from '@/result/Variation'

/** The API body of a form from the URL, or null when the link doesn't hold a complete form. */
function bodyOf(values: FormValues | null): PredictForm | null {
  if (!values) return null
  try {
    return toApiBody(values)
  } catch { // a required reference is missing: the link was cut or edited by hand
    return null
  }
}

function describe(values: FormValues) {
  const when = values.release_month && values.release_year ? `${MONTHS[values.release_month - 1]} ${values.release_year}` : null
  return [values.genres.join(', '), when, values.director?.name && `directed by ${values.director.name}`]
    .filter(Boolean).join(' · ')
}

function Loading() {
  return (
    <div className="grid gap-6" aria-busy="true" aria-live="polite">
      <span className="sr-only">Running the models…</span>
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map(i => <Skeleton key={i} className="h-36 rounded-lg" />)}
      </div>
      <Skeleton className="h-72 rounded-lg" />
      <Skeleton className="h-64 rounded-lg" />
    </div>
  )
}

function Failed({ error, retry, editTo }: { error: unknown; retry: () => void; editTo: string }) {
  const kind = error instanceof ApiError ? error.kind : 'server'
  const message = kind === 'validation'
    ? 'Some of this form needs fixing before it can be predicted.'
    : kind === 'rate_limited' ? RATE_LIMITED : error instanceof Error ? error.message : String(error)
  return (
    <div role="alert" className="bg-card grid justify-items-start gap-3 rounded-lg border p-4">
      <p>{message}</p>
      <div className="flex flex-wrap gap-2">
        {kind !== 'validation' && <Button onClick={retry}>Try again</Button>}
        <Button asChild variant="outline"><Link to={editTo}>Edit the inputs</Link></Button>
      </div>
    </div>
  )
}

export default function PredictResult() {
  const [params] = useSearchParams()
  const encoded = params.get(URL_PARAM) ?? ''
  const encodedBase = params.get(BASE_PARAM)
  const values = useMemo(() => decodeForm(encoded), [encoded])
  const body = useMemo(() => bodyOf(values), [values])
  const base = useMemo(() => bodyOf(decodeForm(encodedBase)), [encodedBase])
  const prediction = usePrediction(body)
  const basePrediction = usePrediction(base && prediction.data ? base : null) // after the main one: one request at a time

  const editTo = `/predict?${new URLSearchParams({ [URL_PARAM]: encoded })}`
  const variationTo = `/predict?${new URLSearchParams({ [URL_PARAM]: encoded, [BASE_PARAM]: encoded })}`
  const withoutBase = `/predict/result?${new URLSearchParams({ [URL_PARAM]: encoded })}`

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      toast.success('Link copied: it opens this result.')
    } catch {
      toast.error("Couldn't copy the link; copy it from the address bar instead.")
    }
  }

  if (!values || !body) {
    return (
      <div className="grid justify-items-start gap-4">
        <PageHeading title="Your prediction">This link doesn't hold a complete film plan.</PageHeading>
        <Button asChild><Link to="/predict">Plan a film</Link></Button>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-start justify-between gap-x-4">
        <PageHeading title="Your prediction">{describe(values)}</PageHeading>
        <Button asChild variant="outline" size="sm" className="print:hidden"><Link to={editTo}><PencilIcon /> Edit inputs</Link></Button>
      </div>
      {prediction.isPending && <Loading />}
      {prediction.isError && <Failed error={prediction.error} retry={() => prediction.refetch()} editTo={editTo} />}
      {prediction.data && (
        <>
          <p className="text-muted-foreground -mt-4 text-sm">
            Money in 2025 US dollars; revenue is worldwide box office. "Likely" ranges run from the 10th to the 90th
            percentile: about 8 in 10 real films land inside.
          </p>
          {base && (
            <VariationStrip base={base} next={body} basePrediction={basePrediction.data} prediction={prediction.data}
              withoutBase={withoutBase} />
          )}
          <Summary prediction={prediction.data} />
          <RangeChart prediction={prediction.data} />
          <Drivers drivers={prediction.data.drivers} />
          <Comparables films={prediction.data.comparables} />
          <Warnings prediction={prediction.data} />
          <Limitations />
          <Accuracy mode={prediction.data.revenue.mode} />
          <div className="flex flex-wrap gap-2 border-t pt-4 print:hidden" role="toolbar" aria-label="Result actions">
            <Button asChild variant="outline"><Link to={editTo}><PencilIcon /> Edit inputs</Link></Button>
            <Button asChild variant="outline"><Link to={variationTo}><ShuffleIcon /> Try a variation</Link></Button>
            <Button variant="outline" onClick={copyLink}><LinkIcon /> Copy link</Button>
            <Button variant="outline" onClick={() => window.print()}><PrinterIcon /> Print or save as PDF</Button>
          </div>
          <p className="text-muted-foreground text-xs">Models version {prediction.data.model_version}; judged as of {prediction.data.as_of}.</p>
        </>
      )}
    </div>
  )
}
