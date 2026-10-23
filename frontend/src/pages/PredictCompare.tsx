// /predict/compare: "what if" for a planned film. The base form travels in ?f= (as on the results page) and up to
// three one-change variants in ?v= (src/compare/variants.ts), so a comparison can be shared or refreshed and Back
// undoes the last change. One POST /predict/compare answers for all of them; below, POST /predict/sweep tries the
// film in every month of its year ("Best release month").
import { ArrowLeftIcon } from 'lucide-react'
import { useEffect, useMemo } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'

import { ApiError } from '@/api/client'
import { useCompare, useMetaOptions, useModelCard, usePrediction, useSweep } from '@/api/hooks'
import { RATE_LIMITED } from '@/api/errors'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CompareView, type Column } from '@/compare/CompareView'
import { monthSweep } from '@/compare/sweep'
import { SweepChart, SweepLoading } from '@/compare/MonthSweep'
import { decodeVariants, encodeVariants, VARIANTS_PARAM, variantText, type Variant } from '@/compare/variants'
import { VariantPicker } from '@/compare/VariantPicker'
import { bodyOf, describeForm, FIELD_LABELS } from '@/form/model'
import { readForm, resultPath, URL_PARAM } from '@/form/persist'
import PageHeading from '@/pages/PageHeading'

function failure(error: unknown) {
  if (!(error instanceof ApiError)) return String(error)
  return error.kind === 'rate_limited' ? RATE_LIMITED : error.message
}

export default function PredictCompare() {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const encoded = params.get(URL_PARAM) ?? ''
  const read = useMemo(() => readForm(encoded), [encoded])
  const body = useMemo(() => bodyOf(read?.form), [read])
  const encodedVariants = params.get(VARIANTS_PARAM)
  const { variants, dropped } = useMemo(() => decodeVariants(encodedVariants), [encodedVariants])

  const options = useMetaOptions()
  const card = useModelCard()
  const base = usePrediction(body)
  const compare = useCompare(body && variants.length ? { base: body, variants: variants.map(v => v.changes) } : null)
  const sweep = useSweep(body ? monthSweep(body) : null)

  useEffect(() => {
    if (location.hash === '#best-month' && sweep.data) document.getElementById('best-month')?.scrollIntoView()
  }, [location.hash, sweep.data])

  const setVariants = (next: Variant[]) => setParams(current => {
    const out = new URLSearchParams(current)
    if (next.length) out.set(VARIANTS_PARAM, encodeVariants(next))
    else out.delete(VARIANTS_PARAM)
    return out
  }, { preventScrollReset: true })

  if (!read || !body) {
    return (
      <div className="grid justify-items-start gap-4">
        <title>Compare versions · Movie Prediction</title>
        <PageHeading title="Compare versions">This link doesn't hold a complete film plan.</PageHeading>
        <Button asChild><Link to="/predict">Plan a film</Link></Button>
      </div>
    )
  }

  const fieldErrors = compare.error instanceof ApiError && compare.error.kind === 'validation' ? compare.error.fieldErrors : {}
  const variantError = (i: number) => {
    const entry = Object.entries(fieldErrors).find(([path]) => path.startsWith(`variants.${i}.`) || path === `variants.${i}`)
    if (!entry) return undefined
    const field = entry[0].split('.')[2] as keyof typeof FIELD_LABELS | undefined
    return `This change can't be predicted: ${field ? `${FIELD_LABELS[field] ?? field} ` : ''}${entry[1]}. Remove it to compare the rest.`
  }
  const otherError = compare.isError && Object.keys(fieldErrors).length === 0
  const columns: Column[] = [
    { key: 'base', title: 'Your film', change: null, prediction: base.data ?? compare.data?.base },
    ...variants.map((v, i): Column => {
      const answer = compare.data?.variants[i]
      return {
        key: `${i}-${encodeVariants([v])}`, title: v.name, change: variantText(v), prediction: answer?.prediction,
        shift: answer ? { budget: answer.differences.budget, revenue: answer.differences.revenue, score: answer.differences.score } : undefined,
        modeChanged: answer?.differences.mode_changed, error: variantError(i) ?? (compare.isError && !otherError ? 'Waiting for the other variants to be fixed.' : undefined),
        onRemove: () => setVariants(variants.filter((_, j) => j !== i)),
      }
    }),
  ]
  const year = body.release_year ?? 0
  const resultTo = resultPath(read.form)

  return (
    <div className="grid gap-6">
      <title>Compare versions · Movie Prediction</title>
      <div className="flex flex-wrap items-start justify-between gap-x-4">
        <PageHeading title="Compare versions">{describeForm(read.form)}</PageHeading>
        <Button asChild variant="outline" size="sm" className="print:hidden">
          <Link to={resultTo}><ArrowLeftIcon /> Back to the result</Link>
        </Button>
      </div>
      {(read.dropped.length > 0 || dropped > 0) && (
        <p role="status" className="-mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm dark:bg-amber-950/30" data-testid="link-notice">
          Part of this link couldn't be read
          {read.dropped.length > 0 && <>: {read.dropped.map(k => FIELD_LABELS[k]).join(', ')} {read.dropped.length === 1 ? 'was' : 'were'} reset</>}
          {dropped > 0 && <>{read.dropped.length > 0 ? ', and ' : ': '}{dropped} {dropped === 1 ? 'variant was' : 'variants were'} left out</>}.
        </p>
      )}

      {options.isPending && <Skeleton className="h-60 rounded-lg" />}
      {options.data && <VariantPicker base={body} options={options.data} added={variants} onAdd={v => setVariants([...variants, v])} />}
      {variants.length === 0 && (
        <p className="text-muted-foreground text-sm">Add a variant above to see what one change does to the ranges.</p>
      )}
      <SlowNotice pending={base.isPending || compare.isFetching || sweep.isPending} />
      {otherError && (
        <div role="alert" className="bg-card grid justify-items-start gap-3 rounded-lg border p-4">
          <p>{failure(compare.error)}</p>
          <Button onClick={() => compare.refetch()}>Try again</Button>
        </div>
      )}
      {base.isError && !compare.data && (
        <div role="alert" className="bg-card grid justify-items-start gap-3 rounded-lg border p-4">
          <p>{failure(base.error)}</p>
          <Button onClick={() => base.refetch()}>Try again</Button>
        </div>
      )}
      <CompareView columns={columns} card={card.data} />

      <section id="best-month" aria-labelledby="best-month-heading" className="bg-card grid scroll-mt-20 gap-4 rounded-lg border p-4 sm:p-6">
        <div>
          <h2 id="best-month-heading" className="text-lg font-semibold">Best release month</h2>
          <p className="text-muted-foreground text-sm">Your film as planned, released in each month of {year}: expected box office and its likely range.</p>
        </div>
        {sweep.isPending && <SweepLoading />}
        {sweep.isError && (
          <div role="alert" className="grid justify-items-start gap-3">
            <p>{failure(sweep.error)}</p>
            <Button variant="outline" onClick={() => sweep.refetch()}>Try again</Button>
          </div>
        )}
        {sweep.data && <SweepChart sweep={sweep.data} chosen={body.release_month ?? 0} card={card.data} year={year} />}
      </section>
    </div>
  )
}
