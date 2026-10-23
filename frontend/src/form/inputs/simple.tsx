// The plain inputs: a select of choices, the runtime (number box + slider), the budget in millions, and the
// synopsis with its character counter.
import { useState } from 'react'

import type { A11y } from '@/form/inputs/FormField'
import { millionsText, shortMoney, toDollars } from '@/form/format'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export function ChoiceSelect<T extends string | number>({ a11y, value, onChange, choices, label, placeholder }: {
  a11y: A11y; value: T | null | ''; onChange: (value: T) => void; choices: readonly T[]
  label?: (choice: T) => string; placeholder: string
}) {
  return (
    <Select value={value === null || value === '' ? '' : String(value)}
      onValueChange={v => onChange(choices.find(c => String(c) === v)!)}>
      <SelectTrigger {...a11y} className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {choices.map(c => <SelectItem key={String(c)} value={String(c)}>{label ? label(c) : String(c)}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}

export function RuntimeInput({ a11y, value, onChange, min, max }: {
  a11y: A11y; value: number | null; onChange: (value: number | null) => void; min: number; max: number
}) {
  return (
    <div className="flex items-center gap-4">
      <div className="relative w-28 shrink-0">
        <Input {...a11y} type="number" inputMode="numeric" min={min} max={max} step={1} className="pr-12"
          value={value ?? ''} onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))} />
        <span className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm">min</span>
      </div>
      <Slider aria-label="Runtime slider" min={min} max={max} step={1} value={[value ?? 110]}
        onValueChange={([v]) => onChange(v)} className={cn('flex-1', value === null && 'opacity-50')} />
    </div>
  )
}

/** The budget in millions of dollars ("40", "2.5"); the form keeps whole dollars. The box keeps its own text, so
 *  "2." can be typed on the way to "2.5", and shows the form's value again when it changes from outside. */
export function BudgetInput({ a11y, value, onChange }: { a11y: A11y; value: number | null; onChange: (value: number | null) => void }) {
  const [text, setText] = useState(() => millionsText(value))
  const shown = toDollars(text) === value ? text : millionsText(value)
  return (
    <div className="flex items-center gap-3">
      <div className="relative w-40">
        <span className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm">$</span>
        <Input {...a11y} type="text" inputMode="decimal" autoComplete="off" placeholder="e.g. 40" className="pr-20 pl-6"
          value={shown}
          onChange={e => {
            const clean = e.target.value.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1').slice(0, 12)
            setText(clean)
            onChange(toDollars(clean))
          }} />
        <span className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm">million</span>
      </div>
      {value !== null && value > 0 && <span className="text-muted-foreground text-sm">= {shortMoney(value)}</span>}
    </div>
  )
}

export function SynopsisInput({ a11y, value, onChange, max }: { a11y: A11y; value: string; onChange: (value: string) => void; max: number }) {
  const length = value.trim().length
  return (
    <div className="grid gap-1">
      <Textarea {...a11y} rows={3} value={value} onChange={e => onChange(e.target.value)}
        placeholder="A retired heist crew reunites for one last job in Lisbon…" />
      <p className={cn('text-right text-xs', length > max ? 'text-destructive' : 'text-muted-foreground')} aria-live="polite">
        {length.toLocaleString('en-US')} / {max.toLocaleString('en-US')}
      </p>
    </div>
  )
}
