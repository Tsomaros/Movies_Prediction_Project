// Multi-select chips (genres, themes): toggle buttons with aria-pressed. Once `max` are picked the rest are
// disabled, so the limit is visible instead of an error after the fact.
import { CheckIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

export function ChipGroup({ id, options, value, onChange, max, label, describedBy, invalid }: {
  id: string
  options: readonly string[]
  value: string[]
  onChange: (value: string[]) => void
  max?: number
  label?: (option: string) => string
  describedBy?: string
  invalid?: boolean
}) {
  const full = max !== undefined && value.length >= max
  return (
    <div id={id} role="group" aria-labelledby={`${id}-label`} aria-describedby={describedBy}
      aria-invalid={invalid || undefined} className="flex flex-wrap gap-2">
      {options.map(option => {
        const on = value.includes(option)
        return (
          <button key={option} type="button" aria-pressed={on} disabled={!on && full}
            onClick={() => onChange(on ? value.filter(v => v !== option) : [...value, option])}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm transition-colors',
              'focus-visible:ring-ring/50 outline-none focus-visible:ring-3 disabled:cursor-not-allowed disabled:opacity-40',
              on ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-accent bg-background',
              invalid && !on && 'border-destructive/60',
            )}>
            {on && <CheckIcon className="size-3.5" aria-hidden />}
            {label ? label(option) : option}
          </button>
        )
      })}
    </div>
  )
}
