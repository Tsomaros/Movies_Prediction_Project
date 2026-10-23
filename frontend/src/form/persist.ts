// Keeping a form: in the URL (to share it) and as a draft in this browser (so a refresh loses nothing).
//
//   encodeForm(values) / decodeForm(text)   -> the ?f= value: the form as JSON in base64url (UTF-8 safe);
//                                              decodeForm returns null for anything that isn't a form
//   readForm(text)                          -> the same, plus the fields it had to drop (a link cut or edited by hand)
//   toBase64Url(text) / fromBase64Url(text) -> the encoding, also used for the compare page's variants
//   loadDraft() / saveDraft(values) / clearDraft()   -> localStorage, wrapped so a blocked storage is just "none"
//   resultPath(values) / comparePath(values) -> the results and compare pages' addresses for a form
//   startingForm(search)                    -> the form a page load starts with: the URL's, else the draft,
//                                              else a fresh one (where it came from, and what the link lost)
import { emptyForm, type FormValues, type NameRef } from '@/form/model'

export const URL_PARAM = 'f'
export const LIKE_PARAM = 'like' // the title of the film a form was started from ("Predict a film like this")
export const DRAFT_KEY = 'movie-prediction:draft'

export function toBase64Url(text: string): string {
  let binary = ''
  for (const byte of new TextEncoder().encode(text)) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function fromBase64Url(text: string): string {
  const binary = atob(text.replace(/-/g, '+').replace(/_/g, '/'))
  return new TextDecoder().decode(Uint8Array.from(binary, c => c.charCodeAt(0)))
}

export const encodeForm = (values: FormValues) => toBase64Url(JSON.stringify(values))

const isNumberOrNull = (v: unknown) => v === null || (typeof v === 'number' && Number.isFinite(v))
const isStrings = (v: unknown) => Array.isArray(v) && v.every(x => typeof x === 'string')
const isRef = (v: unknown): v is NameRef => {
  if (!v || typeof v !== 'object') return false
  const r = v as Record<string, unknown>
  return typeof r.name === 'string' && (r.id === null || (typeof r.id === 'number' && Number.isInteger(r.id) && r.id > 0))
    && (r.n_films === undefined || typeof r.n_films === 'number')
}
const isRefs = (v: unknown) => Array.isArray(v) && v.every(isRef)

const CHECKS: { [K in keyof FormValues]: (v: unknown) => boolean } = {
  genres: isStrings, themes: isStrings, release_year: isNumberOrNull, release_month: isNumberOrNull,
  runtime: isNumberOrNull, language: v => typeof v === 'string', certification: v => typeof v === 'string',
  director: v => v === null || isRef(v), actors: isRefs, companies: isRefs, countries: isStrings,
  franchise: v => v === null || isRef(v), synopsis: v => typeof v === 'string', budget: isNumberOrNull,
}

export type ReadForm = { form: FormValues; dropped: (keyof FormValues)[] }

/** A stored or shared form, checked field by field: a field of the wrong type keeps the fresh form's value (and
 *  is listed in `dropped`), unknown keys are ignored. The form's own rules still run before anything is sent. */
export function parseFormReport(data: unknown): ReadForm | null {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return null
  const out = emptyForm()
  const record = data as Record<string, unknown>
  const dropped: (keyof FormValues)[] = []
  let any = false
  for (const key of Object.keys(CHECKS) as (keyof FormValues)[]) {
    if (!(key in record)) continue
    if (CHECKS[key](record[key])) {
      (out as Record<string, unknown>)[key] = record[key]
      any = true
    } else {
      dropped.push(key)
    }
  }
  return any ? { form: out, dropped } : null
}

export const parseForm = (data: unknown): FormValues | null => parseFormReport(data)?.form ?? null

export function readForm(text: string | null): ReadForm | null {
  if (!text) return null
  try {
    return parseFormReport(JSON.parse(fromBase64Url(text)))
  } catch {
    return null
  }
}

export const decodeForm = (text: string | null): FormValues | null => readForm(text)?.form ?? null

export function loadDraft(): FormValues | null {
  try {
    const text = localStorage.getItem(DRAFT_KEY)
    return text ? parseForm(JSON.parse(text)) : null
  } catch {
    return null
  }
}

export function saveDraft(values: FormValues) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(values))
  } catch { /* storage full or blocked: the URL still holds the form */ }
}

export function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch { /* nothing to clear */ }
}

export type Source = 'link' | 'draft' | 'new'

export function startingForm(search: string): ReadForm & { source: Source } {
  const shared = readForm(new URLSearchParams(search).get(URL_PARAM))
  if (shared) return { ...shared, source: 'link' }
  const draft = loadDraft()
  if (draft) return { form: draft, dropped: [], source: 'draft' }
  return { form: emptyForm(), dropped: [], source: 'new' }
}

export const resultPath = (values: FormValues) => `/predict/result?${new URLSearchParams({ [URL_PARAM]: encodeForm(values) })}`
export const comparePath = (values: FormValues) => `/predict/compare?${new URLSearchParams({ [URL_PARAM]: encodeForm(values) })}`
