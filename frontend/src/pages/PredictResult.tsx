// /predict/result: the results page. The form travels in the URL (?f=, as on the form page), so a result can be
// shared, refreshed or printed. "Compare variations" and "Best release month" open /predict/compare with this form.
//
// Order: the answer (summary cards) -> the ranges to scale with the break-even band -> why (drivers) -> films like
// it -> notes, limitations and accuracy -> actions. The prediction comes from the query cache when the form page
// just asked for it, else from one request; while it loads, skeletons keep the layout still.
import { CalendarIcon, LinkIcon, PencilIcon, PrinterIcon, ShuffleIcon } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { ApiError } from '@/api/client'
import { RATE_LIMITED } from '@/api/errors'
import { usePrediction } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { bodyOf, describeForm, FIELD_LABELS } from '@/form/model'
import { comparePath, readForm, URL_PARAM } from '@/form/persist'
import PageHeading from '@/pages/PageHeading'
import { Comparables } from '@/result/Comparables'
import { Drivers } from '@/result/Drivers'
import { Accuracy, Limitations, Warnings } from '@/result/Notes'
import { RangeChart } from '@/result/RangeChart'
import { Summary } from '@/result/Summary'

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
  const read = useMemo(() => readForm(encoded), [encoded])
  const values = read?.form ?? null
  const body = useMemo(() => bodyOf(values), [values])
  const prediction = usePrediction(body)

  const editTo = `/predict?${new URLSearchParams({ [URL_PARAM]: encoded })}`
  const compareTo = values ? comparePath(values) : '/predict'

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
        <PageHeading title="Your prediction">{describeForm(values)}</PageHeading>
        <Button asChild variant="outline" size="sm" className="print:hidden"><Link to={editTo}><PencilIcon /> Edit inputs</Link></Button>
      </div>
      {read && read.dropped.length > 0 && (
        <p role="status" className="-mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm dark:bg-amber-950/30" data-testid="link-notice">
          Part of this link couldn't be read: {read.dropped.map(k => FIELD_LABELS[k]).join(', ')}{' '}
          {read.dropped.length === 1 ? 'was' : 'were'} reset to the usual value. <Link to={editTo} className="underline">Check the inputs</Link>
        </p>
      )}
      <SlowNotice pending={prediction.isPending} />
      {prediction.isPending && <Loading />}
      {prediction.isError && <Failed error={prediction.error} retry={() => prediction.refetch()} editTo={editTo} />}
      {prediction.data && (
        <>
          <p className="text-muted-foreground -mt-4 text-sm">
            Money in 2025 US dollars; revenue is worldwide box office. "Likely" ranges run from the 10th to the 90th
            percentile: about 8 in 10 real films land inside.
          </p>
          <Summary prediction={prediction.data} />
          <RangeChart prediction={prediction.data} />
          <Drivers drivers={prediction.data.drivers} />
          <Comparables films={prediction.data.comparables} />
          <Warnings prediction={prediction.data} />
          <Limitations />
          <Accuracy mode={prediction.data.revenue.mode} />
          <div className="flex flex-wrap gap-2 border-t pt-4 print:hidden" role="toolbar" aria-label="Result actions">
            <Button asChild variant="outline"><Link to={editTo}><PencilIcon /> Edit inputs</Link></Button>
            <Button asChild variant="outline"><Link to={compareTo}><ShuffleIcon /> Compare variations</Link></Button>
            <Button asChild variant="outline"><Link to={`${compareTo}#best-month`}><CalendarIcon /> Best release month</Link></Button>
            <Button variant="outline" onClick={copyLink}><LinkIcon /> Copy link</Button>
            <Button variant="outline" onClick={() => window.print()}><PrinterIcon /> Print or save as PDF</Button>
          </div>
          <p className="text-muted-foreground text-xs">Models version {prediction.data.model_version}; judged as of {prediction.data.as_of}.</p>
        </>
      )}
    </div>
  )
}
