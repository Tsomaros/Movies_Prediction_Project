// The creator form: one card, two columns on wider screens, the optional fields folded under "More details".
// Rules come from makeSchema (the API's own limits); a 422 from the API lands on the same fields.
// The toolbar on top loads an example, copies a link to this form, or clears it; every change is reported
// through onValuesChange (the page keeps the URL and the draft from it).
import { zodResolver } from '@hookform/resolvers/zod'
import { EraserIcon, LinkIcon, Loader2Icon } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Controller, useForm, type FieldErrors } from 'react-hook-form'

import type { Options, PredictForm } from '@/api/client'
import { applyFieldErrors } from '@/api/errors'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { EXAMPLES } from '@/form/examples'
import { MONTHS } from '@/form/format'
import { ChipGroup } from '@/form/inputs/ChipGroup'
import { CodeCombobox, CodeMultiSelect } from '@/form/inputs/CodeCombobox'
import { FormField } from '@/form/inputs/FormField'
import { NameChips, NamePicker } from '@/form/inputs/NameSearch'
import { BudgetInput, ChoiceSelect, RuntimeInput, SynopsisInput } from '@/form/inputs/simple'
import { messageOf } from '@/form/messages'
import { emptyForm, makeSchema, OPTIONAL_FIELDS, toApiBody, type FormValues } from '@/form/model'

const FIELD_ORDER: (keyof FormValues)[] = ['genres', 'themes', 'release_month', 'release_year', 'runtime', 'language',
  'certification', 'director', 'actors', 'companies', 'countries', 'franchise', 'budget', 'synopsis']
const MORE = 'more'

/** Focus the first field with an error, in form order (custom inputs aren't registered refs, so by id). */
function focusFirstError(errors: FieldErrors<FormValues>) {
  const name = FIELD_ORDER.find(f => errors[f])
  if (!name) return
  const field = document.querySelector(`[data-field="f-${name}"]`)
  const target = field?.querySelector<HTMLElement>('input:not([type="hidden"]):not(:disabled), textarea, button:not(:disabled)')
  field?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
  target?.focus({ preventScroll: true })
}

/** "Genres (2/5)": the count next to the label, so the limit is always in sight. */
function Counted({ label, n, of }: { label: string; n: number; of: string }) {
  return <>{label} <span className="text-muted-foreground font-normal tabular-nums">({n}/{of})</span></>
}

const hasOptional = (values: FormValues) => OPTIONAL_FIELDS.some(f => {
  const v = values[f]
  return Array.isArray(v) ? v.length > 0 : v !== null && v !== ''
})

/** `onSubmit` returns the request; when it fails with a 422 the API's messages land on the fields. */
export function CreatorForm({ options, initial, onSubmit, pending, onValuesChange, onClear, onCopyLink }: {
  options: Options
  initial?: FormValues
  onSubmit: (body: PredictForm) => Promise<unknown>
  pending: boolean
  onValuesChange?: (values: FormValues) => void
  onClear?: () => void
  onCopyLink?: (values: FormValues) => void
}) {
  const schema = useMemo(() => makeSchema(options.fields), [options.fields])
  const spec = useMemo(() => Object.fromEntries(options.fields.map(f => [f.name, f])), [options.fields])
  const start = initial ?? emptyForm()
  const form = useForm<FormValues>({
    resolver: zodResolver(schema), defaultValues: start, mode: 'onSubmit', reValidateMode: 'onChange',
  })
  const { control, handleSubmit, formState: { errors }, setError, reset, subscribe, getValues } = form
  const [more, setMore] = useState(() => (hasOptional(start) ? MORE : ''))
  const [leftover, setLeftover] = useState<string[]>([])

  useEffect(() => { // report every change (the page saves the draft and the URL from it)
    if (!onValuesChange) return
    return subscribe({ formState: { values: true }, callback: ({ values }) => onValuesChange(values) })
  }, [subscribe, onValuesChange])

  const load = (values: FormValues) => {
    reset(values)
    setLeftover([])
    setMore(hasOptional(values) ? MORE : '')
    onValuesChange?.(values) // reset() doesn't notify watch subscribers
  }

  const submit = async (values: FormValues) => {
    setLeftover([])
    try {
      await onSubmit(toApiBody(values))
    } catch (error) {
      const fields = new Set<string>()
      setLeftover(applyFieldErrors(error, setError as never, path => {
        const name = path.split('.')[0] // "actors.2" -> the actors field
        if (!(FIELD_ORDER as string[]).includes(name)) return null
        fields.add(name)
        return name
      }))
      if (OPTIONAL_FIELDS.some(f => fields.has(f))) setMore(MORE)
    }
  }

  const onInvalid = (errs: FieldErrors<FormValues>) => {
    if (OPTIONAL_FIELDS.some(f => errs[f])) setMore(MORE)
    setTimeout(() => focusFirstError(errs)) // after the fold opens
  }
  const maxGenres = spec.genres?.max_items ?? 5
  const maxThemes = spec.themes?.max_items ?? 5
  const [minActors, maxActors] = [spec.actors?.min_items ?? 5, spec.actors?.max_items ?? 10]
  const maxCompanies = spec.companies?.max_items ?? 5
  const maxCountries = spec.countries?.max_items ?? 5

  return (
    <form noValidate aria-label="Creator form" onSubmit={handleSubmit(submit, onInvalid)}
      className="bg-card text-card-foreground grid gap-x-6 gap-y-5 rounded-lg border p-4 shadow-xs sm:grid-cols-2 sm:p-6">
      <div className="flex flex-wrap items-center gap-2 border-b pb-4 sm:col-span-2" role="toolbar" aria-label="Form tools">
        <span className="text-muted-foreground text-sm">Try an example:</span>
        {EXAMPLES.map(example => (
          <Button key={example.key} type="button" variant="outline" size="sm" title={example.description}
            onClick={() => load(example.form)}>
            {example.label}
          </Button>
        ))}
        <span className="flex gap-1 sm:ml-auto">
          {onCopyLink && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onCopyLink(getValues())}><LinkIcon /> Copy link</Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={() => { load(emptyForm()); onClear?.() }}>
            <EraserIcon /> Clear form
          </Button>
        </span>
      </div>
      <Controller control={control} name="genres" render={({ field }) => (
        <FormField id="f-genres" className="sm:col-span-2" error={messageOf(errors.genres)}
          label={<Counted label="Genres" n={field.value.length} of={String(maxGenres)} />}>
          {a => <ChipGroup id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.genres} options={options.genres}
            value={field.value} onChange={field.onChange} max={maxGenres} />}
        </FormField>
      )} />
      <Controller control={control} name="themes" render={({ field }) => (
        <FormField id="f-themes" className="sm:col-span-2" error={messageOf(errors.themes)} hint="What the story is about."
          label={<Counted label="Themes" n={field.value.length} of={String(maxThemes)} />}>
          {a => <ChipGroup id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.themes} options={options.themes}
            value={field.value} onChange={field.onChange} max={maxThemes} label={t => t[0].toUpperCase() + t.slice(1)} />}
        </FormField>
      )} />

      <div className="grid grid-cols-[3fr_2fr] gap-3">
        <Controller control={control} name="release_month" render={({ field }) => (
          <FormField id="f-release_month" label="Release month" error={messageOf(errors.release_month)}>
            {a => <ChoiceSelect a11y={a} value={field.value} onChange={field.onChange} choices={options.months}
              label={m => MONTHS[m - 1]} placeholder="Month" />}
          </FormField>
        )} />
        <Controller control={control} name="release_year" render={({ field }) => (
          <FormField id="f-release_year" label="Year" error={messageOf(errors.release_year)}>
            {a => <ChoiceSelect a11y={a} value={field.value} onChange={field.onChange} choices={options.release_years}
              placeholder="Year" />}
          </FormField>
        )} />
      </div>
      <Controller control={control} name="runtime" render={({ field }) => (
        <FormField id="f-runtime" label="Runtime" error={messageOf(errors.runtime)}>
          {a => <RuntimeInput a11y={a} value={field.value} onChange={field.onChange}
            min={spec.runtime?.min ?? 40} max={spec.runtime?.max ?? 300} />}
        </FormField>
      )} />
      <Controller control={control} name="language" render={({ field }) => (
        <FormField id="f-language" label="Original language" error={messageOf(errors.language)}>
          {a => <CodeCombobox id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.language} kind="language"
            codes={options.languages} value={field.value} onChange={field.onChange} placeholder="Pick a language" />}
        </FormField>
      )} />
      <Controller control={control} name="certification" render={({ field }) => (
        <FormField id="f-certification" label="US rating" error={messageOf(errors.certification)}>
          {a => <ChoiceSelect a11y={a} value={field.value} onChange={field.onChange} choices={options.certifications}
            label={c => (c === 'unrated/unknown' ? 'Unrated / not sure' : c)} placeholder="Pick a rating" />}
        </FormField>
      )} />

      <Controller control={control} name="director" render={({ field }) => (
        <FormField id="f-director" label="Director" error={messageOf(errors.director)}>
          {a => <NamePicker id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.director} kind="director"
            value={field.value} onChange={field.onChange} placeholder="Search directors" />}
        </FormField>
      )} />
      <Controller control={control} name="actors" render={({ field }) => (
        <FormField id="f-actors" className="sm:col-span-2" error={messageOf(errors.actors)}
          label={<Counted label="Top-billed cast" n={field.value.length} of={`${minActors}–${maxActors}`} />}
          hint="In billing order. Someone not in our data can be added as new, with no earlier films.">
          {a => <NameChips id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.actors} kind="actor" numbered
            value={field.value} onChange={field.onChange} max={maxActors} placeholder="Search actors"
            fullText={`${maxActors} actors is the most`} />}
        </FormField>
      )} />

      <Accordion type="single" collapsible value={more} onValueChange={setMore} className="border-t sm:col-span-2">
        <AccordionItem value={MORE} className="border-0">
          <AccordionTrigger className="text-base font-semibold"><span>More details <span className="text-muted-foreground font-normal">(optional)</span></span></AccordionTrigger>
          <AccordionContent className="grid gap-x-6 gap-y-5 pt-1 pb-2 sm:grid-cols-2" forceMount hidden={more !== MORE}>
            <Controller control={control} name="companies" render={({ field }) => (
              <FormField id="f-companies" error={messageOf(errors.companies)}
                label={<Counted label="Production companies" n={field.value.length} of={String(maxCompanies)} />}>
                {a => <NameChips id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.companies} kind="company"
                  value={field.value} onChange={field.onChange} max={maxCompanies} placeholder="Search studios"
                  fullText={`${maxCompanies} studios is the most`} />}
              </FormField>
            )} />
            <Controller control={control} name="countries" render={({ field }) => (
              <FormField id="f-countries" error={messageOf(errors.countries)}
                label={<Counted label="Production countries" n={field.value.length} of={String(maxCountries)} />}>
                {a => <CodeMultiSelect id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.countries} kind="region"
                  codes={options.countries} value={field.value} onChange={field.onChange} max={maxCountries}
                  placeholder="Add a country" />}
              </FormField>
            )} />
            <Controller control={control} name="franchise" render={({ field }) => (
              <FormField id="f-franchise" label="Franchise" error={messageOf(errors.franchise)}
                hint="For a sequel or spin-off. A new name starts a new franchise.">
                {a => <NamePicker id={a.id} describedBy={a['aria-describedby']} invalid={!!errors.franchise} kind="franchise"
                  value={field.value} onChange={field.onChange} placeholder="Search franchises" />}
              </FormField>
            )} />
            <Controller control={control} name="budget" render={({ field }) => (
              <FormField id="f-budget" label="Budget" error={messageOf(errors.budget)}
                hint="In millions of US dollars. Leave it empty and we'll estimate it.">
                {a => <BudgetInput a11y={a} value={field.value} onChange={field.onChange} />}
              </FormField>
            )} />
            <Controller control={control} name="synopsis" render={({ field }) => (
              <FormField id="f-synopsis" label="Synopsis" className="sm:col-span-2" error={messageOf(errors.synopsis)}
                hint="1–3 sentences about the story work best.">
                {a => <SynopsisInput a11y={a} value={field.value} onChange={field.onChange} max={spec.synopsis?.max ?? 2000} />}
              </FormField>
            )} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="grid gap-3 sm:col-span-2">
        {leftover.length > 0 && (
          <div role="alert" className="border-destructive/50 text-destructive rounded-md border p-3 text-sm">
            {leftover.map(m => <p key={m}>{m}</p>)}
          </div>
        )}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" size="lg" disabled={pending} className="sm:w-44">
            {pending && <Loader2Icon className="animate-spin" aria-hidden />}
            {pending ? 'Predicting…' : 'Predict'}
          </Button>
          {pending && <p className="text-muted-foreground text-sm" aria-live="polite">Running the models, this takes a second or two…</p>}
          {!pending && Object.keys(errors).length > 0 && (
            <p className="text-destructive text-sm">Some fields need fixing – see the messages above.</p>
          )}
        </div>
      </div>
    </form>
  )
}
