// /predict: the creator form. Until the Day 11 results page, the API's answer is shown raw under the form.
//
// The form starts from the URL (?f=, a shared link), else this browser's draft, else fresh. While the creator
// types, the URL and the draft follow it (SAVE_MS after the last change), so a refresh or a copied link keeps it.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { useMetaOptions, usePredict } from '@/api/hooks'
import { Button } from '@/components/ui/button'
import { CreatorForm } from '@/form/CreatorForm'
import type { FormValues } from '@/form/model'
import { clearDraft, encodeForm, saveDraft, startingForm, URL_PARAM } from '@/form/persist'
import PageHeading from '@/pages/PageHeading'

export const SAVE_MS = 400

const STARTED_FROM = { link: 'Loaded from a shared link.', draft: 'Your draft from last time is back.', new: null }

export default function Predict() {
  const options = useMetaOptions()
  const predict = usePredict()
  const result = useRef<HTMLElement>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [start] = useState(() => startingForm(`?${searchParams}`))
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    if (predict.data) result.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [predict.data])
  useEffect(() => () => clearTimeout(timer.current), [])

  const keep = useCallback((values: FormValues) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      saveDraft(values)
      setSearchParams({ [URL_PARAM]: encodeForm(values) }, { replace: true, preventScrollReset: true })
    }, SAVE_MS)
  }, [setSearchParams])

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
        Describe the film you have in mind. Everything is about the plan: nothing about how it did after release.
      </PageHeading>
      {STARTED_FROM[start.source] && <p className="text-muted-foreground -mt-4 text-sm">{STARTED_FROM[start.source]}</p>}
      {options.isPending && <p className="text-muted-foreground" aria-live="polite">Loading the form…</p>}
      {options.isError && (
        <div role="alert" className="grid justify-items-start gap-3">
          <p>The form couldn't load: {options.error.message}</p>
          <Button variant="outline" onClick={() => options.refetch()}>Try again</Button>
        </div>
      )}
      {options.data && (
        <CreatorForm options={options.data} initial={start.form} pending={predict.isPending}
          onSubmit={body => predict.mutateAsync(body)} onValuesChange={keep} onClear={clear} onCopyLink={copyLink} />
      )}
      {predict.data && (
        <section ref={result} aria-labelledby="raw-heading" className="grid scroll-mt-20 gap-2">
          <h2 id="raw-heading" className="text-lg font-semibold">Prediction (raw)</h2>
          <p className="text-muted-foreground text-sm">The results page arrives on Day 11; this is the API's answer as is.</p>
          <pre data-testid="raw-prediction" className="bg-muted max-h-[32rem] overflow-auto rounded-md p-4 text-xs">
            {JSON.stringify(predict.data, null, 2)}
          </pre>
        </section>
      )}
    </div>
  )
}
