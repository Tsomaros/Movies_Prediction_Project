// The header search itself (V1.1): the Movies | People switch, the box and its quick results. The desktop header
// shows it inline with a dropdown; the phone overlay (MobileSearch) shows the same box with the results below it.
//
// Mode: a results page decides it (/browse movies, /people people); elsewhere the last mode used (search.ts).
// Text: a results page's ?q=, else empty; any navigation puts it back that way, so picking a result clears it.
// Quick results: the top 5 in the current mode, 250 ms after the last keystroke, from 2 letters or digits. While
// a new answer is on its way the last one stays, faded. Nothing is highlighted until the first ↓, so Enter
// without the arrows always opens the full results page; Enter on a highlighted row opens that row.
// Esc closes the dropdown, a second Esc leaves the box. On a results page, switching the mode opens the other
// results page with the same text (a new history entry, so Back returns).
import { SearchIcon, XIcon } from 'lucide-react'
import { useId, useState, type KeyboardEvent, type RefObject } from 'react'
import { useLocation, useNavigate } from 'react-router'

import type { MovieSummary, PeopleSearchResult } from '@/api/client'
import { DEBOUNCE_MS, QUICK, useOtherModeCount, useQuickSearch } from '@/api/hooks'
import { Skeleton } from '@/components/ui/skeleton'
import { useDebounced } from '@/lib/useDebounced'
import { cn } from '@/lib/utils'
import { initials, nameHue } from '@/movies/people'
import { ModeHint } from '@/search/ModeHint'
import {
  count, MODES, modeFromLocation, readStoredMode, resultsUrl, rolesLine, SEARCH_INPUT_ID, storeMode, usableQuery, type SearchMode,
} from '@/search/search'

const PLACEHOLDER: Record<SearchMode, string> = { movies: 'Search movies…', people: 'Search actors, directors, writers…' }
const LABEL: Record<SearchMode, string> = { movies: 'Movies', people: 'People' }

const thumb = (poster: MovieSummary['poster']) => poster?.small.replace('/w342/', '/w92/') ?? null

function ModeSwitch({ mode, onChange, className }: { mode: SearchMode; onChange: (m: SearchMode) => void; className?: string }) {
  // A radio group: Tab reaches the chosen mode, ← and → switch (and move the focus with them)
  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return
    e.preventDefault()
    onChange(mode === 'movies' ? 'people' : 'movies')
  }
  return (
    <div role="radiogroup" aria-label="Search for" className={cn('bg-muted inline-flex shrink-0 rounded-md p-0.5', className)}>
      {MODES.map(m => (
        <button key={m} type="button" role="radio" aria-checked={m === mode} tabIndex={m === mode ? 0 : -1}
          onClick={() => onChange(m)} onKeyDown={onKeyDown}
          className={cn('rounded px-2.5 py-1 text-xs font-medium outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50',
            m === mode ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
          {LABEL[m]}
        </button>
      ))}
    </div>
  )
}

function MovieRow({ film }: { film: MovieSummary }) {
  const src = thumb(film.poster)
  return (
    <>
      {src ? <img src={src} alt="" loading="lazy" className="bg-muted h-12 w-8 shrink-0 rounded-sm object-cover" />
        : <span aria-hidden className="bg-muted h-12 w-8 shrink-0 rounded-sm" />}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{film.title}</span>
        <span className="text-muted-foreground text-xs">{film.year ?? 'Year unknown'}</span>
      </span>
      {film.score !== null && film.votes > 0 && (
        <span className="bg-secondary text-secondary-foreground shrink-0 rounded px-1.5 py-0.5 text-xs tabular-nums"
          aria-label={`Score ${film.score.toFixed(1)}`}>★ {film.score.toFixed(1)}</span>
      )}
    </>
  )
}

function PersonRow({ person }: { person: PeopleSearchResult }) {
  return (
    <>
      {person.thumb ? <img src={person.thumb} alt="" loading="lazy" className="bg-muted size-10 shrink-0 rounded-full object-cover" /> : (
        <span aria-hidden className="inline-flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
          style={{ backgroundColor: `hsl(${nameHue(person.name)} 45% 38%)` }}>{initials(person.name)}</span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{person.name}</span>
        <span className="text-muted-foreground block truncate text-xs">
          {rolesLine(person.roles)}
          {person.known_for && <> · {person.known_for.title}{person.known_for.year ? ` (${person.known_for.year})` : ''}</>}
        </span>
      </span>
    </>
  )
}

type Props = {
  variant: 'header' | 'overlay'
  inputRef?: RefObject<HTMLInputElement | null>
  /** The overlay closes when a row, the footer or the hint is chosen */
  onDone?: () => void
  /** The overlay replaces its own history entry instead of adding one */
  replace?: boolean
}

export function SearchBox({ variant, inputRef, onDone, replace = false }: Props) {
  const location = useLocation()
  const navigate = useNavigate()
  const listId = `${useId()}-list`
  const urlMode = modeFromLocation(location.pathname)
  const urlQ = urlMode ? new URLSearchParams(location.search).get('q') ?? '' : ''
  const [stored, setStored] = useState(readStoredMode)
  const mode = urlMode ?? stored
  const [text, setText] = useState(urlQ)
  const [open, setOpen] = useState(variant === 'overlay')
  const [active, setActive] = useState(-1)
  const [seen, setSeen] = useState(location.key)
  if (seen !== location.key) { // a navigation: back to the page's own text, dropdown closed
    setSeen(location.key)
    setText(urlQ)
    setActive(-1)
    if (variant === 'header') setOpen(false)
  }

  const term = useDebounced(text, DEBOUNCE_MS)
  const quick = useQuickSearch(mode, term)
  const data = quick.data?.mode === mode ? quick.data : undefined
  const settled = data !== undefined && !quick.isPlaceholderData
  const none = settled && data.total === 0
  const other = useOtherModeCount(mode, term, none)
  const items: (MovieSummary | PeopleSearchResult)[] = data ? data.items.slice(0, QUICK) : []
  const footer = data !== undefined && data.total > 0
  const last = items.length - (footer ? 0 : 1) // the footer is one more row
  const usable = usableQuery(text) !== null
  const showList = (open || variant === 'overlay') && usable
  const goTo = (to: string) => {
    navigate(to, { replace })
    setOpen(false)
    onDone?.()
  }
  const openRow = (i: number) => {
    if (i === items.length) return goTo(seeAll())
    goTo(`/${mode === 'movies' ? 'movies' : 'people'}/${items[i].id}`)
  }
  const seeAll = () => resultsUrl(mode, text, location.pathname === '/browse' ? new URLSearchParams(location.search) : undefined)
  const changeMode = (m: SearchMode) => {
    storeMode(m)
    setStored(m)
    setActive(-1)
    if (urlMode && usable && m !== mode) navigate(resultsUrl(m, text))
    inputRef?.current?.focus()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      setActive(a => e.key === 'ArrowDown' ? Math.min(last, a + 1) : Math.max(-1, a - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (showList && active >= 0 && active <= last) openRow(active)
      else if (usable) goTo(seeAll())
    } else if (e.key === 'Escape' && variant === 'header') {
      if (showList) setOpen(false)
      else e.currentTarget.blur()
    }
  }

  const announce = !usable || !settled ? ''
    : none ? `No ${mode} found${other.data ? `, ${count(other.data, mode === 'movies' ? 'people' : 'movies')} found` : ''}`
    : `${count(data.total, mode)} found`
  const shown = text.trim()
  const panel = (
    <div id={listId} role="listbox" aria-label={`${LABEL[mode]} matching ${shown}`}
      onMouseDown={e => e.preventDefault()} // keep the focus in the box, so a click lands before blur closes it
      className={cn('text-popover-foreground text-sm', variant === 'header'
        ? 'bg-popover absolute top-full right-0 left-0 z-50 mt-1 overflow-hidden rounded-md border py-1 shadow-lg'
        : 'mt-3', quick.isPlaceholderData && 'opacity-60')}>
      {data === undefined && quick.isError ? (
        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <span>Search isn’t available right now.</span>
          <button type="button" onClick={() => quick.refetch()} className="text-primary font-medium underline-offset-4 hover:underline">Retry</button>
        </div>
      ) : data === undefined ? (
        [0, 1, 2].map(i => <div key={i} className="flex items-center gap-3 px-3 py-2"><Skeleton className="h-10 w-8" /><Skeleton className="h-4 flex-1" /></div>)
      ) : none ? (
        <div className="grid gap-1 px-3 py-2">
          <p>No {mode} match ‘{shown}’.</p>
          <ModeHint mode={mode} q={shown} replace={replace} onFollow={() => { setOpen(false); onDone?.() }} />
        </div>
      ) : (
        <>
          {items.map((item, i) => (
            <div key={item.id} id={`${listId}-${i}`} role="option" aria-selected={i === active}
              onMouseEnter={() => setActive(i)} onClick={() => openRow(i)}
              className={cn('flex cursor-pointer items-center gap-3 px-3', variant === 'overlay' ? 'min-h-14 py-2' : 'py-1.5',
                i === active && 'bg-accent text-accent-foreground')}>
              {mode === 'movies' ? <MovieRow film={item as MovieSummary} /> : <PersonRow person={item as PeopleSearchResult} />}
            </div>
          ))}
          <div id={`${listId}-${items.length}`} role="option" aria-selected={active === items.length}
            onMouseEnter={() => setActive(items.length)} onClick={() => openRow(items.length)}
            className={cn('text-primary cursor-pointer border-t px-3 font-medium', variant === 'overlay' ? 'min-h-11 py-3' : 'py-2',
              active === items.length && 'bg-accent')}>
            See all {data.total.toLocaleString('en-US')} results for ‘{shown}’
          </div>
        </>
      )}
    </div>
  )

  return (
    <div className={cn('relative', variant === 'overlay' && 'grid gap-3')}>
      <div className="flex items-center gap-2">
        <ModeSwitch mode={mode} onChange={changeMode} />
        <div className={cn('border-input bg-background focus-within:border-ring focus-within:ring-ring/50 flex min-w-0 flex-1 items-center gap-1.5 rounded-md border px-2 focus-within:ring-3',
          variant === 'overlay' ? 'h-11' : 'h-8')}>
          <SearchIcon className="text-muted-foreground size-4 shrink-0" aria-hidden />
          <input ref={inputRef} id={variant === 'header' ? SEARCH_INPUT_ID : undefined} type="search" value={text}
            placeholder={PLACEHOLDER[mode]} aria-label={mode === 'movies' ? 'Search movies' : 'Search people'}
            role="combobox" aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
            aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
            autoComplete="off" enterKeyHint="search"
            onChange={e => { setText(e.target.value); setOpen(true); setActive(-1) }}
            onFocus={() => setOpen(true)} onBlur={() => variant === 'header' && setOpen(false)} onKeyDown={onKeyDown}
            className="placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-sm outline-none [&::-webkit-search-cancel-button]:hidden" />
          {text && (
            <button type="button" aria-label="Clear search" onMouseDown={e => e.preventDefault()}
              onClick={() => { setText(''); setActive(-1); inputRef?.current?.focus() }}
              className={cn('text-muted-foreground hover:text-foreground rounded outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                variant === 'overlay' ? 'p-2' : 'p-0.5')}>
              <XIcon className="size-4" />
            </button>
          )}
        </div>
      </div>
      {showList && panel}
      <p className="sr-only" aria-live="polite">{showList ? announce : ''}</p>
    </div>
  )
}
