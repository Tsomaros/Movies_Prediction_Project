// Adding a variant on the compare page: quick presets, or one field changed by hand. Every variant changes exactly
// one field, so each difference has one clear cause. Numbers are checked against the API's own limits
// (/meta/options) before anything is sent; the API checks again.
import { PlusIcon } from 'lucide-react'
import { useId, useRef, useState, type ReactNode } from 'react'

import type { FormChanges, Options, PredictForm } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  changeText, MAX_VARIANTS, PRESETS, presetAction, type ChangeField, type PresetId, type Variant,
} from '@/compare/variants'
import { codeName, MONTHS } from '@/form/format'
import { NameSearch, Chip } from '@/form/inputs/NameSearch'
import type { NameRef } from '@/form/model'

const CONTROL = 'border-input bg-card dark:bg-input/30 h-9 w-full rounded-md border px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring'

const MANUAL: { field: ChangeField; label: string }[] = [
  { field: 'release_month', label: 'Release month' },
  { field: 'release_year', label: 'Release year' },
  { field: 'runtime', label: 'Runtime' },
  { field: 'budget', label: 'Budget' },
  { field: 'certification', label: 'Rating' },
  { field: 'language', label: 'Original language' },
  { field: 'director', label: 'Director' },
  { field: 'franchise', label: 'Franchise' },
]

const refBody = (ref: NameRef) => (ref.id !== null ? { id: ref.id, name: ref.name } : { name: ref.name.trim() })

/** The changes for a field and its editor's text, or the reason they can't be used. */
function toChanges(field: ChangeField, text: string, ref: NameRef | null, base: PredictForm, options: Options): FormChanges | string {
  const spec = options.fields.find(f => f.name === field)
  if (field === 'director' || field === 'franchise') {
    if (!ref) return `Pick a ${field} first`
    return { [field]: refBody(ref) }
  }
  if (field === 'certification' || field === 'language') {
    if (!text) return 'Pick a value first'
    return text === base[field] ? "That's what your film has already" : { [field]: text }
  }
  if (field === 'budget' && text === 'none') {
    return base.budget == null ? 'The budget is already left out' : { budget: null }
  }
  const n = field === 'budget' ? Number(text) * 1e6 : Number(text)
  if (text.trim() === '' || !Number.isFinite(n)) return 'Enter a number first'
  if (field !== 'budget' && !Number.isInteger(n)) return 'Use a whole number'
  if (spec?.min != null && n < spec.min) return `The lowest allowed is ${field === 'budget' ? `$${spec.min.toLocaleString('en-US')}` : spec.min}`
  if (spec?.max != null && n > spec.max) return `The highest allowed is ${field === 'budget' ? `$${(spec.max / 1e6).toLocaleString('en-US')}M` : spec.max}`
  if (n === base[field]) return "That's what your film has already"
  return { [field]: field === 'budget' ? Math.round(n) : n }
}

function Editor({ field, id, text, setText, refValue, setRef, options }: {
  field: ChangeField; id: string; text: string; setText: (t: string) => void
  refValue: NameRef | null; setRef: (r: NameRef | null) => void; options: Options
}): ReactNode {
  switch (field) {
    case 'release_month':
      return (
        <select id={id} className={CONTROL} value={text} onChange={e => setText(e.target.value)}>
          <option value="">Pick a month</option>
          {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </select>
      )
    case 'certification':
      return (
        <select id={id} className={CONTROL} value={text} onChange={e => setText(e.target.value)}>
          <option value="">Pick a rating</option>
          {options.certifications.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      )
    case 'language':
      return (
        <select id={id} className={CONTROL} value={text} onChange={e => setText(e.target.value)}>
          <option value="">Pick a language</option>
          {options.languages.map(l => <option key={l.code} value={l.code}>{codeName('language', l.code)}</option>)}
        </select>
      )
    case 'budget':
      return (
        <div className="grid gap-2">
          <div className="flex items-center gap-2">
            <input id={id} type="number" inputMode="decimal" min={0} step="any" placeholder="e.g. 40" className={CONTROL}
              value={text === 'none' ? '' : text} disabled={text === 'none'} onChange={e => setText(e.target.value)} />
            <span className="text-muted-foreground shrink-0 text-sm">million $</span>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={text === 'none'} onChange={e => setText(e.target.checked ? 'none' : '')} />
            Leave the budget out (it is estimated)
          </label>
        </div>
      )
    case 'director':
    case 'franchise':
      return refValue ? (
        <div><Chip label={refValue.name} onRemove={() => setRef(null)}>{refValue.name}</Chip></div>
      ) : (
        <NameSearch id={id} kind={field} onPick={setRef}
          placeholder={field === 'director' ? 'Search directors' : 'Search franchises'} />
      )
    default:
      return (
        <input id={id} type="number" inputMode="numeric" className={CONTROL} value={text}
          placeholder={field === 'runtime' ? 'Minutes' : 'Year'} onChange={e => setText(e.target.value)} />
      )
  }
}

export function VariantPicker({ base, options, added, onAdd }: {
  base: PredictForm; options: Options; added: Variant[]; onAdd: (variant: Variant) => void
}) {
  const count = added.length
  const id = useId()
  const [field, setField] = useState<ChangeField | ''>('')
  const [text, setText] = useState('')
  const [ref, setRef] = useState<NameRef | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [presetName, setPresetName] = useState<string | null>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  const full = count >= MAX_VARIANTS

  const choose = (next: ChangeField | '', name: string | null = null) => {
    setField(next)
    setText('')
    setRef(null)
    setProblem(null)
    setPresetName(name)
  }

  const preset = (presetId: PresetId, name: string) => {
    const action = presetAction(presetId, base, options, added)
    if ('changes' in action) onAdd({ name, changes: action.changes })
    else if ('pick' in action) {
      choose(action.pick, name)
      setTimeout(() => editorRef.current?.querySelector('input')?.focus())
    }
  }

  const add = () => {
    if (!field) return
    const changes = toChanges(field, text, ref, base, options)
    if (typeof changes === 'string') {
      setProblem(changes)
      return
    }
    const [key, value] = Object.entries(changes)[0]
    if (added.some(v => JSON.stringify(v.changes) === JSON.stringify(changes))) {
      setProblem('You already have this variant')
      return
    }
    onAdd({ name: presetName ?? changeText(key as ChangeField, value), changes })
    choose('')
  }

  if (full) {
    return <p className="text-muted-foreground text-sm">You're comparing {MAX_VARIANTS} variants, the most at once. Remove one to try another.</p>
  }

  return (
    <section aria-labelledby={`${id}-heading`} className="bg-card grid gap-4 rounded-lg border p-4 print:hidden">
      <div>
        <h2 id={`${id}-heading`} className="font-semibold">Add a variant ({count} of {MAX_VARIANTS})</h2>
        <p className="text-muted-foreground text-sm">Each variant changes one thing, so you can see what that one change does.</p>
      </div>
      <div className="grid gap-2">
        <h3 className="text-sm font-medium">Quick ideas</h3>
        <ul className="flex flex-wrap gap-2">
          {PRESETS.map(p => {
            const action = presetAction(p.id, base, options, added)
            if ('hidden' in action) return null
            const reason = 'disabled' in action ? action.disabled : null
            return (
              <li key={p.id} className="grid gap-0.5">
                <Button type="button" variant="outline" size="sm" disabled={reason !== null}
                  aria-describedby={reason ? `${id}-${p.id}-why` : undefined} onClick={() => preset(p.id, p.name)}>
                  {p.name}
                </Button>
                {reason && <span id={`${id}-${p.id}-why`} className="text-muted-foreground text-xs">{reason}</span>}
              </li>
            )
          })}
        </ul>
      </div>
      <div className="grid gap-2">
        <label htmlFor={`${id}-field`} className="text-sm font-medium">Or change one thing yourself</label>
        <div className="grid gap-2 sm:grid-cols-[12rem_1fr_auto] sm:items-start">
          <select id={`${id}-field`} className={CONTROL} value={field}
            onChange={e => choose(e.target.value as ChangeField | '')}>
            <option value="">Pick what to change</option>
            {MANUAL.map(m => <option key={m.field} value={m.field}>{m.label}</option>)}
          </select>
          <div ref={editorRef} className="grid gap-1">
            {field && (
              <>
                <label htmlFor={`${id}-value`} className="sr-only">New {MANUAL.find(m => m.field === field)?.label.toLowerCase()}</label>
                <Editor field={field} id={`${id}-value`} text={text} setText={t => { setText(t); setProblem(null) }}
                  refValue={ref} setRef={r => { setRef(r); setProblem(null) }} options={options} />
              </>
            )}
            {problem && <p role="alert" className="text-destructive text-sm">{problem}</p>}
          </div>
          <Button type="button" onClick={add} disabled={!field}><PlusIcon /> Add variant</Button>
        </div>
      </div>
    </section>
  )
}
