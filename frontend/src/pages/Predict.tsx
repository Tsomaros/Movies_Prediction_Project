// /predict: the creator form. A successful prediction opens the results page (/predict/result?f=…), which finds
// the answer already in the query cache.
//
// The form starts from the URL (?f=, a shared link), else this browser's draft, else fresh. While the creator
// types, the URL and the draft follow it (SAVE_MS after the last change), so a refresh or a copied link keeps it.
// "Try a variation" on the results page adds ?base= (the version to compare with), which is kept until the next
// result shows the difference.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import type { PredictForm } from '@/api/client'

import { useMetaOptions, usePredict } from '@/api/hooks'
import { Button } from '@/components/ui/button'
import { CreatorForm } from '@/form/CreatorForm'
import type { FormValues } from '@/form/model'
import { BASE_PARAM, clearDraft, LIKE_PARAM, encodeForm, resultPath, saveDraft, startingForm, URL_PARAM } from '@/form/persist'
import PageHeading from '@/pages/PageHeading'

export const SAVE_MS = 400

const STARTED_FROM = { link: 'Loaded from a shared link.', draft: 'Your draft from last time is back.', new: null }

export default function Predict() {
  const options = useMetaOptions()
  const predict = usePredict()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [start] = useState(() => startingForm(`?${searchParams}`))
  const [base] = useState(() => searchParams.get(BASE_PARAM))
  const [like] = useState(() => (start.source === 'link' ? searchParams.get(LIKE_PARAM) : null))
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const keep = useCallback((values: FormValues) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      saveDraft(values)
      setSearchParams({ [URL_PARAM]: encodeForm(values), ...(base ? { [BASE_PARAM]: base } : {}) },
        { replace: true, preventScrollReset: true })
    }, SAVE_MS)
  }, [setSearchParams, base])

  const submit = useCallback(async (body: PredictForm, values: FormValues) => {
    await predict.mutateAsync(body) // a 422 throws back into the form; the answer is cached for the results page
    clearTimeout(timer.current)
    saveDraft(values)
    navigate(resultPath(values, base))
  }, [predict, navigate, base])

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
      {base ? (
        <p className="text-muted-foreground -mt-4 text-sm" data-testid="variation-hint">
          Trying a variation: change one thing and predict again to see what it does.
        </p>
      ) : like ? (
        <p className="text-muted-foreground -mt-4 text-sm" data-testid="like-hint">
          Started from {like}: change what makes your film different, then predict.
        </p>
      ) : STARTED_FROM[start.source] && <p className="text-muted-foreground -mt-4 text-sm">{STARTED_FROM[start.source]}</p>}
      {options.isPending && <p className="text-muted-foreground" aria-live="polite">Loading the form…</p>}
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
