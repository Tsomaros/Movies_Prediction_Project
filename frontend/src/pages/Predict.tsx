// /predict: the creator form. A successful prediction opens the results page (/predict/result?f=…), which finds
// the answer already in the query cache.
//
// The form starts from the URL (?f=, a shared link), else this browser's draft, else fresh. While the creator
// types, the URL and the draft follow it (SAVE_MS after the last change), so a refresh or a copied link keeps it.
// A link that lost fields (cut or edited by hand) still opens: the readable fields load, and a notice names the rest.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import type { PredictForm } from '@/api/client'

import { useMetaOptions, usePredict } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CreatorForm } from '@/form/CreatorForm'
import { FIELD_LABELS, type FormValues } from '@/form/model'
import { clearDraft, LIKE_PARAM, encodeForm, resultPath, saveDraft, startingForm, URL_PARAM } from '@/form/persist'
import PageHeading from '@/pages/PageHeading'

export const SAVE_MS = 400

// What a prediction gives back, shown above the form
const POINTS = [
  { title: 'Budget, revenue and audience score', text: 'Each as a range: low, middle and high, right about 8 times in 10.' },
  { title: 'Why', text: 'The main reasons behind each estimate, in plain words.' },
  { title: 'Films like yours', text: 'Five past films with their real budget, revenue and score.' },
]

const STARTED_FROM = { link: 'Loaded from a shared link.', draft: 'Your draft from last time is back.', new: null }

export default function Predict() {
  const options = useMetaOptions()
  const predict = usePredict()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [start] = useState(() => startingForm(`?${searchParams}`))
  const [like] = useState(() => (start.source === 'link' ? searchParams.get(LIKE_PARAM) : null))
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const keep = useCallback((values: FormValues) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      saveDraft(values)
      setSearchParams({ [URL_PARAM]: encodeForm(values) }, { replace: true, preventScrollReset: true })
    }, SAVE_MS)
  }, [setSearchParams])

  const submit = useCallback(async (body: PredictForm, values: FormValues) => {
    await predict.mutateAsync(body) // a 422 throws back into the form; the answer is cached for the results page
    clearTimeout(timer.current)
    saveDraft(values)
    navigate(resultPath(values))
  }, [predict, navigate])

  const clear = useCallback(() => {
    clearTimeout(timer.current)
    clearDraft()
    setSearchParams({}, { replace: true, preventScrollReset: true })
  }, [setSearchParams])

  const copyLink = useCallback(async (values: FormValues) => { // from the values: the URL may be a keystroke behind
    const link = new URL(window.location.href)
    link.search = new URLSearchParams({ [URL_PARAM]: encodeForm(values) }).toString()
    try {
      await navigator.clipboard.writeText(link.toString())
      toast.success('Link copied: it opens this form as it is now.')
    } catch {
      toast.error("Couldn't copy the link; copy it from the address bar instead.")
    }
  }, [])

  return (
    <div className="grid gap-8">
      <PageHeading title="Plan a film">
        How might your film do? Describe the film you have in mind and see what 79,000 films from 1960 to 2025 suggest
        about its budget, box office and audience score. Everything is about the plan: nothing about how it did after release.
      </PageHeading>
      {like ? (
        <p className="text-muted-foreground -mt-4 text-sm" data-testid="like-hint">
          Started from {like}: change what makes your film different, then predict.
        </p>
      ) : STARTED_FROM[start.source] && <p className="text-muted-foreground -mt-4 text-sm">{STARTED_FROM[start.source]}</p>}
      {start.dropped.length > 0 && (
        <p role="status" className="-mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm dark:bg-amber-950/30" data-testid="link-notice">
          Part of this link couldn't be read: {start.dropped.map(k => FIELD_LABELS[k]).join(', ')}{' '}
          {start.dropped.length === 1 ? 'starts' : 'start'} from the usual value. The rest is filled in.
        </p>
      )}
      <ul className="-mt-2 grid gap-3 sm:grid-cols-3 print:hidden" aria-label="What you get" data-testid="predict-intro">
        {POINTS.map(p => (
          <li key={p.title} className="rounded-lg border p-3">
            <h2 className="text-sm font-medium">{p.title}</h2>
            <p className="text-muted-foreground mt-1 text-sm">{p.text}</p>
          </li>
        ))}
      </ul>
      <SlowNotice pending={options.isPending || predict.isPending} />
      {options.isPending && (
        <div className="grid min-h-svh content-start gap-4" aria-busy="true">
          <p className="text-muted-foreground" aria-live="polite">Loading the form…</p>
          <Skeleton className="h-40 rounded-lg" /><Skeleton className="h-64 rounded-lg" />
        </div>
      )}
      {options.isError && (
        <div role="alert" className="grid justify-items-start gap-3">
          <p>The form couldn't load: {options.error.message}</p>
          <Button variant="outline" onClick={() => options.refetch()}>Try again</Button>
        </div>
      )}
      {options.data && (
        <CreatorForm options={options.data} initial={start.form} pending={predict.isPending}
          onSubmit={submit} onValuesChange={keep} onClear={clear} onCopyLink={copyLink} />
      )}
    </div>
  )
}
