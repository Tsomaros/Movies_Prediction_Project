// The creator form's data: its values, the Zod rules (built from the API's own field specs) and the API body.
//
//   FormValues, NameRef                -> what the inputs edit; a person/studio/franchise is {id, name}, id null
//                                         for a name typed by hand ("new": no track record)
//   emptyForm(), DEFAULTS              -> a fresh form: runtime, release date and language prefilled (DEFAULTS),
//                                         the rest left for the creator
//   makeSchema(fields)                 -> Zod rules mirroring ml/features/contract.py, with every limit read
//                                         from GET /meta/options `fields`, so no number is copied by hand
//   toApiBody(values)                  -> the POST /predict body: empty optional fields left out, references
//                                         as {id, name} or {name}
//   bodyOf(values)                     -> the same for a form read from a link, or null when it isn't complete
//   describeForm(values)               -> one line for a page heading: "Drama · October 2026 · directed by …"
//   OPTIONAL_FIELDS                    -> the fields under "More details"
//   FIELD_LABELS                       -> each API field's name in words ("release month", "cast")
//
// The API checks everything again (contract.validate); these rules only stop a bad form before it is sent
// and say what to fix next to the field.
import { z } from 'zod'

import type { FieldSpec, PredictForm } from '@/api/client'
import { MONTHS, shortMoney } from '@/form/format'

type Genre = NonNullable<PredictForm['genres']>[number] // the 19 names come from /meta/options at run time

export type NameRef ={ id: number | null; name: string; n_films?: number }

export type FormValues = {
  genres: string[]
  themes: string[]
  release_year: number | null
  release_month: number | null
  runtime: number | null
  language: string
  certification: string
  director: NameRef | null
  actors: NameRef[] // billing order
  companies: NameRef[]
  countries: string[]
  franchise: NameRef | null
  synopsis: string
  budget: number | null
}

export const OPTIONAL_FIELDS = ['companies', 'countries', 'franchise', 'synopsis', 'budget'] as const

/** Typical values, so a quick "what if" needs fewer clicks: 110 minutes, June of next year, English. */
export const DEFAULTS = { runtime: 110, release_month: 6, language: 'en', yearsAhead: 1 } as const

export function emptyForm(today = new Date()): FormValues {
  return {
    genres: [], themes: [], release_year: today.getFullYear() + DEFAULTS.yearsAhead, release_month: DEFAULTS.release_month,
    runtime: DEFAULTS.runtime, language: DEFAULTS.language, certification: '', director: null, actors: [],
    companies: [], countries: [], franchise: null, synopsis: '', budget: null,
  }
}

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`
const thousands = (n: number) => n.toLocaleString('en-US')

/** The spec of one field; the form can't be built without the API's specs, so a missing one is a bug. */
function spec(fields: FieldSpec[], name: string) {
  const f = fields.find(x => x.name === name)
  if (!f) throw new Error(`/meta/options has no field "${name}"`)
  return { ...f, min: f.min ?? null, max: f.max ?? null, min_items: f.min_items ?? null, max_items: f.max_items ?? null }
}

function listRule(f: { min_items: number | null; max_items: number | null }, what: string, many?: string) {
  const min = f.min_items ?? 0
  const max = f.max_items ?? Infinity
  return (items: unknown[], ctx: z.RefinementCtx) => {
    if (items.length < min) ctx.addIssue({ code: 'custom', message: min === 1 ? `Pick at least one ${what}` : `Pick at least ${count(min, what, many)}` })
    if (items.length > max) ctx.addIssue({ code: 'custom', message: `Pick at most ${count(max, what, many)}` })
  }
}

function numberRule(f: { min: number | null; max: number | null }, { required, whole, label, format = String }:
  { required: string | null; whole: boolean; label: string; format?: (n: number) => string }) {
  return (value: number | null, ctx: z.RefinementCtx) => {
    if (value === null) {
      if (required) ctx.addIssue({ code: 'custom', message: required })
      return
    }
    if (!Number.isFinite(value) || (whole && !Number.isInteger(value))) {
      ctx.addIssue({ code: 'custom', message: `${label} must be a whole number` })
    } else if ((f.min !== null && value < f.min) || (f.max !== null && value > f.max)) {
      ctx.addIssue({ code: 'custom', message: `${label} must be between ${format(f.min ?? 0)} and ${format(f.max ?? 0)}` })
    }
  }
}

const nameRef = z.object({ id: z.number().int().positive().nullable(), name: z.string(), n_films: z.number().optional() })
const filled = (ref: NameRef | null) => ref !== null && (ref.id !== null || ref.name.trim() !== '')
const sameRef = (a: NameRef, b: NameRef) =>
  a.id !== null && b.id !== null ? a.id === b.id : a.name.trim().toLowerCase() === b.name.trim().toLowerCase()

export function makeSchema(fields: FieldSpec[]) {
  const genres = spec(fields, 'genres')
  const themes = spec(fields, 'themes')
  const actors = spec(fields, 'actors')
  const certification = spec(fields, 'certification')
  const language = new RegExp(spec(fields, 'language').pattern ?? '^[a-z]{2}$')
  const country = new RegExp(spec(fields, 'countries').pattern ?? '^[A-Z]{2}$')
  const synopsis = spec(fields, 'synopsis')
  const budget = spec(fields, 'budget')

  return z.object({
    genres: z.array(z.string()).superRefine(listRule(genres, 'genre')),
    themes: z.array(z.string()).superRefine(listRule(themes, 'theme')),
    release_year: z.number().nullable().superRefine(
      numberRule(spec(fields, 'release_year'), { required: 'Pick a release year', whole: true, label: 'The year' })),
    release_month: z.number().nullable().superRefine(
      numberRule(spec(fields, 'release_month'), { required: 'Pick a release month', whole: true, label: 'The month' })),
    runtime: z.number().nullable().superRefine(numberRule(spec(fields, 'runtime'),
      { required: 'Enter a runtime in minutes', whole: true, label: 'Runtime', format: n => `${n} minutes` })),
    language: z.string().superRefine((v, ctx) => {
      if (!v) ctx.addIssue({ code: 'custom', message: 'Pick the original language' })
      else if (!language.test(v)) ctx.addIssue({ code: 'custom', message: 'Pick a language from the list' })
    }),
    certification: z.string().superRefine((v, ctx) => {
      if (!(certification.choices ?? []).includes(v)) ctx.addIssue({ code: 'custom', message: 'Pick a rating' })
    }),
    director: nameRef.nullable().superRefine((v, ctx) => {
      if (!filled(v)) ctx.addIssue({ code: 'custom', message: 'Pick a director or type a new name' })
    }),
    actors: z.array(nameRef).superRefine((list, ctx) => {
      const min = actors.min_items ?? 0
      if (list.length < min) {
        const more = min - list.length
        ctx.addIssue({ code: 'custom', message: list.length === 0
          ? `Add the ${min} top-billed actors` : `Add ${more} more ${more === 1 ? 'actor' : 'actors'} (at least ${min})` })
      }
      if (list.length > (actors.max_items ?? Infinity)) ctx.addIssue({ code: 'custom', message: `At most ${actors.max_items} actors` })
      if (list.some((ref, i) => list.slice(0, i).some(other => sameRef(other, ref))))
        ctx.addIssue({ code: 'custom', message: 'The same actor is in the cast twice' })
    }),
    companies: z.array(nameRef).superRefine(listRule(spec(fields, 'companies'), 'company', 'companies')),
    countries: z.array(z.string()).superRefine((list, ctx) => {
      listRule(spec(fields, 'countries'), 'country', 'countries')(list, ctx)
      if (list.some(c => !country.test(c))) ctx.addIssue({ code: 'custom', message: 'Pick countries from the list' })
    }),
    franchise: nameRef.nullable(),
    synopsis: z.string().superRefine((v, ctx) => {
      if (synopsis.max !== null && v.trim().length > synopsis.max)
        ctx.addIssue({ code: 'custom', message: `Keep the synopsis under ${thousands(synopsis.max)} characters` })
    }),
    budget: z.number().nullable().superRefine(
      numberRule(budget, { required: null, whole: false, label: 'The budget', format: shortMoney })),
  }) satisfies z.ZodType<FormValues>
}

const refBody = (ref: NameRef) => (ref.id !== null ? { id: ref.id, name: ref.name } : { name: ref.name.trim() })

/** Call only with values that passed makeSchema: the required fields are known to be filled. */
export function toApiBody(v: FormValues): PredictForm {
  const body: PredictForm = {
    genres: v.genres as Genre[], release_year: v.release_year!, release_month: v.release_month!, runtime: v.runtime!,
    language: v.language, certification: v.certification as PredictForm['certification'],
    director: refBody(v.director!), actors: v.actors.map(refBody), themes: v.themes,
  }
  if (v.companies.length) body.companies = v.companies.map(refBody)
  if (v.countries.length) body.countries = v.countries
  if (v.franchise && filled(v.franchise)) body.franchise = refBody(v.franchise)
  if (v.synopsis.trim()) body.synopsis = v.synopsis.trim()
  if (v.budget !== null) body.budget = v.budget
  return body
}

/** The API body of a form from a link, or null when it doesn't hold a complete form (a required reference is
 *  missing: the link was cut or edited by hand). */
export function bodyOf(values: FormValues | null | undefined): PredictForm | null {
  if (!values) return null
  try {
    return toApiBody(values)
  } catch {
    return null
  }
}

export function describeForm(values: FormValues) {
  const when = values.release_month && values.release_year ? `${MONTHS[values.release_month - 1]} ${values.release_year}` : null
  return [values.genres.join(', '), when, values.director?.name && `directed by ${values.director.name}`]
    .filter(Boolean).join(' · ')
}

export const FIELD_LABELS: Record<keyof PredictForm, string> = {
  genres: 'genres', themes: 'themes', release_year: 'release year', release_month: 'release month',
  runtime: 'runtime', language: 'language', certification: 'rating', director: 'director', actors: 'cast',
  companies: 'studios', countries: 'countries', franchise: 'franchise', synopsis: 'synopsis', budget: 'budget',
}
