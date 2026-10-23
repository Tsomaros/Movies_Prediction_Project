// The compare page's variants: each one changes exactly one field of the base form, so every difference has one
// clear cause. They live in the URL (?v=, base64url JSON like ?f=), so a comparison can be shared or refreshed.
//
//   Variant                         -> {name, changes}: changes has one field, null clearing an optional one
//   encodeVariants(v) / decodeVariants(text) -> the ?v= value; decoding drops anything malformed and counts it
//   PRESETS, presetAction(id, base, options, added) -> the quick variants and what each does for this film: its
//                                       changes, "pick" (the franchise needs a name) or why it doesn't apply
//                                       (including "already added")
//   changeText(field, value)        -> a variant's change in words: "Released in December", "Budget $100M"
//   meaningful(target, shift, card, mode) -> whether a change is bigger than the uncertainty (the model card's
//                                       thresholds: 10% of the median validation range); null without a card
//   driverChanges(base, variant)    -> the revenue drivers that moved: "Release timing: now a slight boost (was a
//                                       moderate drag)"
import type { Driver, FormChanges, ModelCard, Options, PredictForm, Prediction } from '@/api/client'
import { codeName, MONTHS } from '@/form/format'
import { FIELD_LABELS } from '@/form/model'
import { fromBase64Url, toBase64Url } from '@/form/persist'
import { money } from '@/result/format'

export const VARIANTS_PARAM = 'v'
export const MAX_VARIANTS = 3

export type ChangeField = keyof FormChanges
export type Variant = { name: string; changes: FormChanges }
type Ref = NonNullable<PredictForm['director']>

const isRef = (v: unknown) => {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return false
  const r = v as Record<string, unknown>
  return typeof r.name === 'string' && (r.id === undefined || r.id === null || (typeof r.id === 'number' && Number.isInteger(r.id)))
}
const isNumber = (v: unknown) => typeof v === 'number' && Number.isFinite(v)

/** The fields a variant may change, with a light shape check (the API checks the values themselves). */
const CHECKS: Partial<Record<ChangeField, (v: unknown) => boolean>> = {
  release_month: isNumber, release_year: isNumber, runtime: isNumber,
  budget: v => v === null || isNumber(v),
  certification: v => typeof v === 'string', language: v => typeof v === 'string',
  director: isRef, franchise: v => v === null || isRef(v),
  actors: v => Array.isArray(v) && v.length > 0 && v.every(isRef),
}

export const encodeVariants = (variants: Variant[]) => toBase64Url(JSON.stringify(variants))

export function decodeVariants(text: string | null): { variants: Variant[]; dropped: number } {
  if (!text) return { variants: [], dropped: 0 }
  let data: unknown
  try {
    data = JSON.parse(fromBase64Url(text))
  } catch {
    return { variants: [], dropped: 1 }
  }
  if (!Array.isArray(data)) return { variants: [], dropped: 1 }
  const variants: Variant[] = []
  for (const item of data) {
    const v = item as { name?: unknown; changes?: unknown }
    const changes = v && typeof v === 'object' && v.changes && typeof v.changes === 'object' ? v.changes as Record<string, unknown> : null
    const keys = changes ? Object.keys(changes) : []
    const check = keys.length === 1 ? CHECKS[keys[0] as ChangeField] : undefined
    if (typeof v?.name === 'string' && v.name.length <= 80 && check && check(changes![keys[0]]) && variants.length < MAX_VARIANTS) {
      variants.push({ name: v.name, changes: changes as FormChanges })
    }
  }
  return { variants, dropped: data.length - variants.length }
}

// ---------------------------------------------------------------- presets

export type PresetId = 'holiday' | 'franchise' | 'double-budget' | 'unknown-cast' | 'pg13'
export type PresetAction = { changes: FormChanges } | { pick: 'franchise' } | { disabled: string } | { hidden: true }

export const PRESETS: { id: PresetId; name: string; field: ChangeField }[] = [
  { id: 'holiday', name: 'Holiday release', field: 'release_month' },
  { id: 'franchise', name: 'Make it a franchise', field: 'franchise' },
  { id: 'double-budget', name: 'Double the budget', field: 'budget' },
  { id: 'unknown-cast', name: 'Unknown cast', field: 'actors' },
  { id: 'pg13', name: 'PG-13 instead of R', field: 'certification' },
]

export const UNKNOWN_ACTOR = (i: number) => `New actor ${i + 1}`
const isKnown = (ref: Ref) => typeof ref === 'number' || (typeof ref === 'object' && ref.id != null)

export function presetAction(id: PresetId, base: PredictForm, options: Options, added: Variant[] = []): PresetAction {
  const action = presetFor(id, base, options)
  const same = (v: Variant) => 'changes' in action ? JSON.stringify(v.changes) === JSON.stringify(action.changes)
    : 'pick' in action && action.pick in v.changes
  return !('hidden' in action) && added.some(same) ? { disabled: 'Already added' } : action
}

function presetFor(id: PresetId, base: PredictForm, options: Options): PresetAction {
  switch (id) {
    case 'holiday':
      return base.release_month === 12 ? { disabled: 'Already a December release' } : { changes: { release_month: 12 } }
    case 'franchise':
      return base.franchise ? { disabled: 'Already part of a franchise' } : { pick: 'franchise' }
    case 'double-budget': {
      const max = options.fields.find(f => f.name === 'budget')?.max ?? Infinity
      if (base.budget == null) return { disabled: 'Add a budget to the form first' }
      if (base.budget * 2 > max) return { disabled: `Twice the budget is over ${money(max)}` }
      return { changes: { budget: base.budget * 2 } }
    }
    case 'unknown-cast': {
      const actors = base.actors ?? []
      if (!actors.some(isKnown)) return { disabled: 'The cast is already new to our data' }
      return { changes: { actors: actors.map((_, i) => ({ name: UNKNOWN_ACTOR(i) })) } }
    }
    case 'pg13':
      return base.certification === 'R' ? { changes: { certification: 'PG-13' } } : { hidden: true }
  }
}

// ---------------------------------------------------------------- words

const refName = (ref: Ref) => (typeof ref === 'object' ? ref.name ?? `#${ref.id}` : String(ref))
const isNew = (ref: Ref) => typeof ref === 'object' && ref.id == null

export function changeText(field: ChangeField, value: unknown): string {
  switch (field) {
    case 'release_month': return `Released in ${MONTHS[(value as number) - 1] ?? value}`
    case 'release_year': return `Released in ${value}`
    case 'runtime': return `${value} minutes long`
    case 'budget': return value == null ? 'Budget left out (estimated)' : `Budget ${money(value as number)}`
    case 'certification': return `Rated ${value}`
    case 'language': return `In ${codeName('language', value as string)}`
    case 'director': return `Directed by ${refName(value as Ref)}${isNew(value as Ref) ? ' (new)' : ''}`
    case 'franchise': return value == null ? 'Not part of a franchise' : `Part of ${refName(value as Ref)}`
    case 'actors': {
      const list = value as Ref[]
      return list.every(isNew) ? `A cast of ${list.length} unknowns` : 'A different cast'
    }
    default: return `A different ${FIELD_LABELS[field as keyof PredictForm] ?? field}`
  }
}

export function variantText(variant: Variant): string {
  const [field, value] = Object.entries(variant.changes)[0] ?? []
  return field ? changeText(field as ChangeField, value) : variant.name
}

// ---------------------------------------------------------------- honest differences

export type Target = 'budget' | 'revenue' | 'score'
export type Shift = { ratio?: number | null; points?: number | null }

/** True when the change is at least the threshold, false when it is within the uncertainty, null without a card. */
export function meaningful(target: Target, shift: Shift, card: ModelCard | undefined, revenueMode: 'given' | 'estimated'): boolean | null {
  if (!card) return null
  const u = card.uncertainty
  if (target === 'score') return Math.abs(shift.points ?? 0) >= u.score.points
  const threshold = target === 'budget' ? u.budget.ratio : revenueMode === 'estimated' ? u.revenue_estimated.ratio : u.revenue.ratio
  const ratio = shift.ratio ?? 1
  return Math.max(ratio, 1 / ratio) >= threshold
}

// ---------------------------------------------------------------- what moved

type Effect = Pick<Driver, 'direction' | 'strength'> | undefined

function effects(prediction: Prediction, target: Target) {
  const d = prediction.drivers[target]
  return new Map([...d.up, ...d.down].map(x => [x.group, x] as const))
}

const effectText = (e: Effect) => (e ? `a ${e.strength} ${e.direction === 'up' ? 'boost' : 'drag'}` : 'no clear effect')
const STRENGTH = { strong: 3, moderate: 2, slight: 1 } as const

/** The drivers whose direction or strength differs between two predictions, strongest now first (at most `max`). */
export function driverChanges(base: Prediction, variant: Prediction, target: Target = 'revenue', max = 3): string[] {
  const before = effects(base, target)
  const after = effects(variant, target)
  const groups = new Set([...before.keys(), ...after.keys()])
  return [...groups]
    .map(group => ({ group, b: before.get(group), a: after.get(group) }))
    .filter(({ a, b }) => a?.direction !== b?.direction || a?.strength !== b?.strength)
    .sort((x, y) => (y.a ? STRENGTH[y.a.strength] : 0) - (x.a ? STRENGTH[x.a.strength] : 0))
    .slice(0, max)
    .map(({ a, b }) => `${(a ?? b)!.label}: now ${effectText(a)} (was ${effectText(b)})`)
}
