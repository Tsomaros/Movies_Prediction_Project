// Names typed straight into the box (directors, actors, studios, franchises), with suggestions from the API
// 250 ms after the last keystroke, and a pick shown as a removable chip.
//
//   NameSearch   -> the search box alone (a combobox with its listbox); calls onPick with the chosen name
//   NamePicker   -> one name: the box until a name is picked, then its chip (director, franchise)
//   NameChips    -> several names: chips (numbered for the cast) plus the box for the next one, up to `max`
//
// The suggestions appear only once the search for the current text is done, with the top match active, so
// Enter never picks a stale match or "new" while suggestions are on their way. The last option is always
// "Use '<name>' as a new person": someone our data doesn't know (no track record). Typed text that isn't
// picked is never sent; a hint says so when the box loses focus with text in it.
import { Loader2Icon, PlusIcon, XIcon } from 'lucide-react'
import { useId, useState, type KeyboardEvent, type ReactNode } from 'react'

import type { NameKind } from '@/api/client'
import { useNameSearch } from '@/api/hooks'
import { Input } from '@/components/ui/input'
import { filmCount } from '@/form/format'
import type { NameRef } from '@/form/model'
import { cn } from '@/lib/utils'

const NEW_WORD: Record<NameKind, string> = { director: 'person', actor: 'person', company: 'studio', franchise: 'franchise' }
const sameName = (a: NameRef, b: NameRef) =>
  a.id !== null && b.id !== null ? a.id === b.id : a.name.trim().toLowerCase() === b.name.trim().toLowerCase()

type SearchProps = {
  id: string
  kind: NameKind
  onPick: (ref: NameRef) => void
  placeholder: string
  exclude?: NameRef[]
  disabled?: boolean
  describedBy?: string
  invalid?: boolean
}

export function NameSearch({ id, kind, onPick, placeholder, exclude = [], disabled, describedBy, invalid }: SearchProps) {
  const listId = `${useId()}-list`
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const search = useNameSearch(kind, text)
  const typed = text.trim()
  const settled = typed !== '' && !search.typing && !search.isFetching
  const matches = settled ? (search.data ?? []).filter(m => !exclude.some(e => e.id === m.id)) : []
  const newOne: NameRef = { id: null, name: typed }
  const items: NameRef[] = settled
    ? [...matches.map(m => ({ id: m.id, name: m.name, n_films: m.n_films })),
       ...(exclude.some(e => sameName(e, newOne)) ? [] : [newOne])]
    : []
  const showList = open && typed !== ''
  const current = Math.min(active, items.length - 1)

  const pick = (ref: NameRef) => {
    onPick(ref)
    setText('')
    setActive(0)
  }
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      setActive(Math.max(0, Math.min(items.length - 1, current + (e.key === 'ArrowDown' ? 1 : -1))))
    } else if (e.key === 'Enter') {
      if (typed) e.preventDefault() // never submit the form from a half-typed name
      if (showList && items[current]) pick(items[current])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }
  const hintId = `${id}-typed`
  const leftOver = !open && typed !== '' && !disabled

  return (
    <div className="relative grid gap-1">
      <Input id={id} type="text" value={text} placeholder={placeholder} disabled={disabled} autoComplete="off"
        role="combobox" aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
        aria-activedescendant={showList && items[current] ? `${listId}-${current}` : undefined}
        aria-describedby={[describedBy, leftOver ? hintId : null].filter(Boolean).join(' ') || undefined}
        aria-invalid={invalid || undefined}
        onChange={e => { setText(e.target.value); setOpen(true); setActive(0) }}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={onKeyDown} />
      {showList && (
        <ul id={listId} role="listbox" aria-label={`Suggestions for ${placeholder.toLowerCase()}`}
          className="bg-popover text-popover-foreground absolute top-full right-0 left-0 z-20 mt-1 max-h-72 overflow-y-auto rounded-md border py-1 shadow-lg">
          {!settled && (
            <li className="text-muted-foreground flex items-center gap-2 px-3 py-2 text-sm" aria-live="polite">
              <Loader2Icon className="size-3.5 animate-spin" aria-hidden /> Searching…
            </li>
          )}
          {search.isError && <li className="text-destructive px-3 py-2 text-sm">Search failed. Try again in a moment.</li>}
          {settled && matches.length === 0 && <li className="text-muted-foreground px-3 py-2 text-sm">No matches in our data</li>}
          {items.map((ref, i) => (
            <li key={ref.id ?? 'new'} id={`${listId}-${i}`} role="option" aria-selected={i === current}
              onMouseDown={e => e.preventDefault()} // keep the focus, so the click lands before blur closes the list
              onMouseEnter={() => setActive(i)} onClick={() => pick(ref)}
              className={cn('flex cursor-pointer flex-col px-3 py-1.5', i === current && 'bg-accent text-accent-foreground')}>
              {ref.id !== null ? (
                <>
                  <span className="truncate">{ref.name}</span>
                  <span className="text-muted-foreground text-xs">{filmCount(kind, ref.n_films ?? 0)}</span>
                </>
              ) : (
                <>
                  <span className="flex items-center gap-1 truncate"><PlusIcon className="size-3.5" aria-hidden />Use “{typed}” as a new {NEW_WORD[kind]}</span>
                  <span className="text-muted-foreground text-xs">No earlier films in our data</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {leftOver && (
        <p id={hintId} className="text-muted-foreground text-xs">
          Pick a name from the list or add it as new. Typed text alone isn't used.
        </p>
      )}
    </div>
  )
}

export function Chip({ children, label, onRemove }: { children: ReactNode; label: string; onRemove: () => void }) {
  return (
    <span className="bg-secondary text-secondary-foreground inline-flex items-center gap-1 rounded-full py-1 pr-1 pl-3 text-sm">
      {children}
      <button type="button" onClick={onRemove} aria-label={`Remove ${label}`}
        className="hover:bg-background/60 focus-visible:ring-ring/50 rounded-full p-0.5 outline-none focus-visible:ring-3">
        <XIcon className="size-3.5" />
      </button>
    </span>
  )
}

function ChipText({ kind, value, prefix }: { kind: NameKind; value: NameRef; prefix?: string }) {
  return (
    <>
      <span>{prefix}{value.name}</span>
      <span className="text-xs opacity-70">{value.id === null ? 'new' : value.n_films !== undefined ? filmCount(kind, value.n_films) : ''}</span>
    </>
  )
}

type PickerProps = Omit<SearchProps, 'onPick' | 'exclude'>

export function NamePicker({ value, onChange, ...search }: PickerProps & { value: NameRef | null; onChange: (v: NameRef | null) => void }) {
  if (value) {
    return (
      <div className="flex min-h-9 items-center" id={search.id} tabIndex={-1}>
        <Chip label={value.name} onRemove={() => onChange(null)}><ChipText kind={search.kind} value={value} /></Chip>
      </div>
    )
  }
  return <NameSearch {...search} onPick={onChange} />
}

export function NameChips({ value, onChange, max, numbered, fullText, ...search }: PickerProps & {
  value: NameRef[]; onChange: (v: NameRef[]) => void; max: number; numbered?: boolean; fullText: string
}) {
  const full = value.length >= max
  return (
    <div className="grid gap-2">
      <NameSearch {...search} placeholder={full ? fullText : search.placeholder} disabled={full} exclude={value}
        onPick={ref => onChange([...value, ref])} />
      {value.length > 0 && (
        <ol className="flex flex-wrap gap-2" aria-label="Chosen">
          {value.map((ref, i) => (
            <li key={ref.id ?? `new:${ref.name}`}>
              <Chip label={ref.name} onRemove={() => onChange(value.filter((_, j) => j !== i))}>
                <ChipText kind={search.kind} value={ref} prefix={numbered ? `${i + 1}. ` : undefined} />
              </Chip>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
