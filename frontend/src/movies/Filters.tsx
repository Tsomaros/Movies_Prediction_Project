// The browse filters: genre, release window (Just released | Coming soon), years, original language and lowest score. The menus are the same shadcn/Radix
// Select as the creator form's (FilterSelect, also the sort menu); the years are number boxes. Every change goes
// to the URL through `onChange` (and back to page 1); a year is applied when the box loses focus or on Enter.
import { useState, type ReactNode } from 'react'

import type { Options } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { codeName } from '@/form/format'
import { SCORE_STEPS, WHENS, type BrowseState, type When } from '@/movies/browse'

const CONTROL = 'border-input bg-card dark:bg-input/30 h-9 w-full rounded-md border px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring'

const ANY = 'any' // Radix Select can't hold an empty value: "Any genre" and the like use this one

/** A menu like the form's. `any` adds a first choice for "no filter", sent back as null. */
export function FilterSelect({ id, label, value, onChange, choices, any, className }: {
  id?: string; label?: string; value: string | null; onChange: (value: string | null) => void
  choices: readonly { value: string; label: string }[]; any?: string; className?: string
}) {
  return (
    <Select value={value ?? ANY} onValueChange={v => onChange(v === ANY ? null : v)}>
      <SelectTrigger id={id} aria-label={label} className={className ?? 'bg-card h-9 w-full'}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {any && <SelectItem value={ANY}>{any}</SelectItem>}
        {choices.map(c => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      {children}
    </div>
  )
}

function YearBox({ id, value, placeholder, onCommit }: {
  id: string; value: number | null; placeholder: string; onCommit: (year: number | null) => void
}) {
  const [text, setText] = useState(value === null ? '' : String(value))
  const [shown, setShown] = useState(value)
  if (shown !== value) { // the URL changed (e.g. "Clear filters"): follow it
    setShown(value)
    setText(value === null ? '' : String(value))
  }
  const commit = () => {
    const n = Number(text)
    const year = text.trim() === '' || !Number.isInteger(n) || n < 1900 || n > 2100 ? null : n
    if (year === null) setText('')
    if (year !== value) onCommit(year)
  }
  return (
    <input id={id} type="number" inputMode="numeric" min={1900} max={2100} placeholder={placeholder} value={text}
      onChange={e => setText(e.target.value)} onBlur={commit} onKeyDown={e => { if (e.key === 'Enter') commit() }}
      className={CONTROL} />
  )
}

export function Filters({ state, options, onChange, onClear, idPrefix = 'f' }: {
  state: BrowseState; options: Options | undefined; onChange: (patch: Partial<BrowseState>) => void
  onClear: () => void; idPrefix?: string
}) {
  const id = (name: string) => `${idPrefix}-${name}`
  return (
    <div className="grid gap-4" role="group" aria-label="Filters">
      <Field id={id('genre')} label="Genre">
        <FilterSelect id={id('genre')} value={state.genre} any="Any genre" onChange={genre => onChange({ genre })}
          choices={(options?.genres ?? []).map(g => ({ value: g, label: g }))} />
      </Field>
      <Field id={id('when')} label="Release">
        <FilterSelect id={id('when')} value={state.when} any="Any release date" onChange={when => onChange({ when: when as When | null })}
          choices={WHENS} />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field id={id('from')} label="From year">
          <YearBox id={id('from')} value={state.yearFrom} placeholder="1960" onCommit={yearFrom => onChange({ yearFrom })} />
        </Field>
        <Field id={id('to')} label="To year">
          <YearBox id={id('to')} value={state.yearTo} placeholder="2025" onCommit={yearTo => onChange({ yearTo })} />
        </Field>
      </div>
      <Field id={id('lang')} label="Original language">
        <FilterSelect id={id('lang')} value={state.language} any="Any language" onChange={language => onChange({ language })}
          choices={(options?.languages ?? []).map(l => ({ value: l.code, label: codeName('language', l.code) }))} />
      </Field>
      <Field id={id('score')} label="Audience score">
        <FilterSelect id={id('score')} value={state.scoreMin === null ? null : String(state.scoreMin)} any="Any score"
          onChange={s => onChange({ scoreMin: s === null ? null : Number(s) })}
          choices={SCORE_STEPS.map(s => ({ value: String(s), label: `${s}+ (any number of votes)` }))} />
      </Field>
      <Button variant="outline" size="sm" onClick={onClear}>Clear filters</Button>
    </div>
  )
}
