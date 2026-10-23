// A searchable list of ISO codes with their names in the browser's words (Intl.DisplayNames) and how many
// films in our data have each: the original language (one) and the production countries (several, as chips).
import { ChevronsUpDownIcon, XIcon } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { codeName, formatFilms, type CodeKind } from '@/form/format'
import { cn } from '@/lib/utils'

export type CodeCount = { code: string; films: number }

function CodeList({ kind, codes, selected, onSelect, disabled }: {
  kind: CodeKind; codes: CodeCount[]; selected: string[]; onSelect: (code: string) => void; disabled?: (code: string) => boolean
}) {
  return (
    <Command>
      <CommandInput placeholder={kind === 'language' ? 'Search languages…' : 'Search countries…'} />
      <CommandList>
        <CommandEmpty>Nothing found.</CommandEmpty>
        <CommandGroup>
          {codes.map(({ code, films }) => (
            <CommandItem key={code} value={`${codeName(kind, code)} ${code}`} data-checked={selected.includes(code)}
              disabled={disabled?.(code)} onSelect={() => onSelect(code)}>
              <span className="truncate">{codeName(kind, code)}</span>
              <span className="text-muted-foreground ml-auto text-xs">{formatFilms(films)}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </Command>
  )
}

type Common = { id: string; kind: CodeKind; codes: CodeCount[]; placeholder: string; describedBy?: string; invalid?: boolean }

export function CodeCombobox({ value, onChange, ...p }: Common & { value: string; onChange: (code: string) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button id={p.id} type="button" variant="outline" role="combobox" aria-expanded={open}
          aria-labelledby={`${p.id}-label ${p.id}`} aria-describedby={p.describedBy} aria-invalid={p.invalid}
          className={cn('h-9 w-full justify-between font-normal', !value && 'text-muted-foreground')}>
          <span className="truncate">{value ? codeName(p.kind, value) : p.placeholder}</span>
          <ChevronsUpDownIcon className="opacity-50" aria-hidden />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-64 p-0" align="start">
        <CodeList kind={p.kind} codes={p.codes} selected={value ? [value] : []}
          onSelect={code => { onChange(code); setOpen(false) }} />
      </PopoverContent>
    </Popover>
  )
}

export function CodeMultiSelect({ value, onChange, max, ...p }:
  Common & { value: string[]; onChange: (codes: string[]) => void; max: number }) {
  const [open, setOpen] = useState(false)
  const full = value.length >= max
  return (
    <div className="grid gap-2">
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Chosen countries">
          {value.map(code => (
            <li key={code}>
              <Badge variant="secondary" className="h-7 gap-1 pr-1 text-sm">
                {codeName(p.kind, code)}
                <button type="button" className="hover:bg-muted rounded-full p-0.5" aria-label={`Remove ${codeName(p.kind, code)}`}
                  onClick={() => onChange(value.filter(c => c !== code))}>
                  <XIcon className="size-3.5" />
                </button>
              </Badge>
            </li>
          ))}
        </ul>
      )}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button id={p.id} type="button" variant="outline" role="combobox" aria-expanded={open} disabled={full}
            aria-labelledby={`${p.id}-label ${p.id}`} aria-describedby={p.describedBy} aria-invalid={p.invalid}
            className="text-muted-foreground h-9 w-full justify-between font-normal">
            <span className="truncate">{full ? `${max} is the most` : p.placeholder}</span>
            <ChevronsUpDownIcon className="opacity-50" aria-hidden />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-(--radix-popover-trigger-width) min-w-64 p-0" align="start">
          <CodeList kind={p.kind} codes={p.codes} selected={value}
            onSelect={code => {
              onChange(value.includes(code) ? value.filter(c => c !== code) : [...value, code])
              setOpen(false)
            }}
            disabled={code => full && !value.includes(code)} />
        </PopoverContent>
      </Popover>
    </div>
  )
}
