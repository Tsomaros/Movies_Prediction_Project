// The browse filters: genre, years, original language and lowest score. Native selects and number boxes, so
// they work the same with a keyboard, a screen reader and a phone's own pickers. Every change goes to the URL
// through `onChange` (and back to page 1); a year is applied when the box loses focus or on Enter.
import { useState, type ReactNode } from 'react'

import type { Options } from '@/api/client'
import { Button } from '@/components/ui/button'
import { codeName } from '@/form/format'
import { SCORE_STEPS, type BrowseState } from '@/movies/browse'

const CONTROL = 'border-input bg-card dark:bg-input/30 h-9 w-full rounded-md border px-2 text-sm focus-visible:outline-2 focus-visible:outline-ring'

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
        <select id={id('genre')} className={CONTROL} value={state.genre ?? ''}
          onChange={e => onChange({ genre: e.target.value || null })}>
          <option value="">Any genre</option>
          {(options?.genres ?? []).map(g => <option key={g} value={g}>{g}</option>)}
        </select>
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
        <select id={id('lang')} className={CONTROL} value={state.language ?? ''}
          onChange={e => onChange({ language: e.target.value || null })}>
          <option value="">Any language</option>
          {(options?.languages ?? []).map(l => <option key={l.code} value={l.code}>{codeName('language', l.code)}</option>)}
        </select>
      </Field>
      <Field id={id('score')} label="Audience score">
        <select id={id('score')} className={CONTROL} value={state.scoreMin ?? ''}
          onChange={e => onChange({ scoreMin: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Any score</option>
          {SCORE_STEPS.map(s => <option key={s} value={s}>{s}+ (any number of votes)</option>)}
        </select>
      </Field>
      <Button variant="outline" size="sm" onClick={onClear}>Clear filters</Button>
    </div>
  )
}
