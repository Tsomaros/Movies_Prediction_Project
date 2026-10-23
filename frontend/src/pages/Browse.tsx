// /browse: search and browse the 79,199 films. Everything is in the URL (src/movies/browse.ts): the search
// (applied 300 ms after the last keystroke), the filters, the sort and the page, so a link or the back button
// always shows the same films. Filters sit in a sidebar from `lg`, in a drawer on smaller screens; the grid
// size or list view is remembered in this browser. The curated rows have their own page, /movies.
import { LayoutGridIcon, ListIcon, SearchIcon, SlidersHorizontalIcon, XIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useMetaOptions, useMovies } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { codeName } from '@/form/format'
import { useDebounced } from '@/lib/useDebounced'
import { cn } from '@/lib/utils'
import {
  activeFilters, browseResets, EMPTY, loadView, readBrowse, saveView, SORTS, toQuery, type BrowseState, type View, VIEWS, writeBrowse,
} from '@/movies/browse'
import { Filters } from '@/movies/Filters'
import { MovieCard, MovieListItem } from '@/movies/MovieCard'
import { Pager } from '@/movies/Pager'
import PageHeading from '@/pages/PageHeading'

export const SEARCH_MS = 300
const EAGER = 6 // the first row of posters is the page's largest paint: load it at once

const GRID: Record<Exclude<View, 'list'>, string> = {
  small: 'grid-cols-3 sm:grid-cols-5 lg:grid-cols-6',
  medium: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4',
  large: 'grid-cols-2 lg:grid-cols-3',
}
const VIEW_LABELS: Record<View, string> = { small: 'Small posters', medium: 'Medium posters', large: 'Large posters', list: 'List' }

function ViewPicker({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  return (
    <div role="radiogroup" aria-label="Show films as" className="bg-muted inline-flex rounded-md p-0.5">
      {VIEWS.map(v => (
        <button key={v} type="button" role="radio" aria-checked={view === v} aria-label={VIEW_LABELS[v]} title={VIEW_LABELS[v]}
          onClick={() => onChange(v)}
          className={cn('inline-flex h-8 items-center gap-1 rounded px-2 text-xs',
            view === v ? 'bg-background shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
          {v === 'list' ? <ListIcon className="size-4" aria-hidden /> : (
            <><LayoutGridIcon className={cn(v === 'small' ? 'size-3' : v === 'medium' ? 'size-3.5' : 'size-4')} aria-hidden />
              <span className="hidden sm:inline">{v[0].toUpperCase()}</span></>
          )}
        </button>
      ))}
    </div>
  )
}

export default function Browse() {
  const [params, setParams] = useSearchParams()
  const options = useMetaOptions()
  const read = readBrowse(params)
  const resets = options.isPending ? [] : browseResets(params, options.data?.genres) // once the genres are known
  const unknownGenre = read.genre !== null && (!options.data || !options.data.genres.includes(read.genre))
  const state = options.data && unknownGenre ? { ...read, genre: null } : read
  const movies = useMovies(toQuery(state), !unknownGenre || !options.isPending) // an odd genre waits for the list of genres
  const [view, setView] = useState<View>(loadView)
  const [text, setText] = useState(state.q)
  const typed = useDebounced(text, SEARCH_MS)
  const [drawer, setDrawer] = useState(false)

  const go = (next: BrowseState, replace = false) =>
    setParams(writeBrowse(next), { replace, preventScrollReset: replace })
  const change = (patch: Partial<BrowseState>) => go({ ...state, ...patch, page: 1 })
  const clear = () => { setText(''); go({ ...EMPTY, sort: state.sort }) }

  useEffect(() => { // the search box drives ?q= once typing pauses
    if (typed.trim() !== state.q.trim()) go({ ...state, q: typed, page: 1 }, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a new typed value should write the URL
  }, [typed])
  const [shownQ, setShownQ] = useState(state.q)
  if (shownQ !== state.q) { // the URL changed by other means (back button, a chip): the box follows
    setShownQ(state.q)
    if (state.q.trim() !== text.trim()) setText(state.q)
  }

  const chooseView = (v: View) => { setView(v); saveView(v) }
  const languageName = (code: string) => codeName('language', code)
  const active = activeFilters(state, languageName)
  const hrefFor = (page: number) => `/browse?${writeBrowse({ ...state, page })}`
  const data = movies.data

  return (
    <div className="grid gap-6">
      <PageHeading title="Browse films">
        Search and filter every film in our TMDB data, released from 1960 to 2025.
      </PageHeading>

      <div className="relative -mt-4">
        <SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden />
        <Input type="search" aria-label="Search films" placeholder="Search titles and plots…" value={text}
          onChange={e => setText(e.target.value)} className="h-11 pl-9 text-base" />
      </div>

      {resets.length > 0 && (
        <p role="status" className="-mt-2 rounded-md bg-amber-50 px-3 py-2 text-sm dark:bg-amber-950/30" data-testid="link-notice">
          Part of this link couldn't be read, so the {resets.join(', ')} {resets.length === 1 ? 'was' : 'were'} left at the usual value.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
        <aside className="hidden lg:block" aria-label="Filter films">
          <Filters state={state} options={options.data} onChange={change} onClear={clear} idPrefix="side" />
        </aside>

        <div className="grid content-start gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Sheet open={drawer} onOpenChange={setDrawer}>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm" className="lg:hidden">
                  <SlidersHorizontalIcon /> Filters{active.length > 0 && ` (${active.length})`}
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="overflow-y-auto p-4">
                <SheetHeader className="p-0">
                  <SheetTitle>Filters</SheetTitle>
                  <SheetDescription>Results update as you choose.</SheetDescription>
                </SheetHeader>
                <Filters state={state} options={options.data} onChange={change} onClear={clear} idPrefix="drawer" />
              </SheetContent>
            </Sheet>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Sort</span>
              <select aria-label="Sort by" value={state.sort} onChange={e => change({ sort: e.target.value as BrowseState['sort'] })}
                className="border-input bg-background h-8 rounded-md border px-2 text-sm">
                {SORTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </label>
            <div className="ml-auto"><ViewPicker view={view} onChange={chooseView} /></div>
          </div>

          {active.length > 0 && (
            <ul aria-label="Active filters" className="flex flex-wrap gap-2">
              {active.map(f => (
                <li key={f.key}>
                  <button type="button" onClick={() => { if (f.key === 'q') setText(''); change({ [f.key]: EMPTY[f.key] }) }}
                    aria-label={`Remove filter ${f.label}`}
                    className="bg-secondary text-secondary-foreground inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs">
                    {f.label} <XIcon className="size-3" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <SlowNotice pending={movies.isPending} />
          {movies.isPending && (
            <div className={cn('grid gap-4', view === 'list' ? '' : GRID[view])} aria-busy="true">
              <span className="sr-only">Loading films…</span>
              {Array.from({ length: 12 }, (_, i) => <Skeleton key={i} className={view === 'list' ? 'h-24' : 'aspect-[2/3]'} />)}
            </div>
          )}
          {movies.isError && (
            <div role="alert" className="grid justify-items-start gap-3 rounded-lg border p-4">
              <p>The films couldn't load: {movies.error.message}</p>
              <Button variant="outline" onClick={() => movies.refetch()}>Try again</Button>
            </div>
          )}
          {data && data.items.length === 0 && (
            <div className="grid justify-items-start gap-3 rounded-lg border p-6" data-testid="no-results">
              <p className="font-medium">No films match{state.page > 1 ? ' on this page' : ''}.</p>
              {active.length > 0 ? (
                <>
                  <p className="text-muted-foreground text-sm">Try removing a filter:</p>
                  <div className="flex flex-wrap gap-2">
                    {active.map(f => (
                      <Button key={f.key} variant="outline" size="sm"
                        onClick={() => { if (f.key === 'q') setText(''); change({ [f.key]: EMPTY[f.key] }) }}>
                        Remove {f.label}
                      </Button>
                    ))}
                    <Button size="sm" onClick={clear}>Clear all</Button>
                  </div>
                </>
              ) : state.page > 1 ? <Link to="/browse" className="text-primary underline">Back to page 1</Link> : null}
            </div>
          )}
          {data && data.items.length > 0 && (
            <>
              <p className="text-muted-foreground text-sm" aria-live="polite">
                {data.total.toLocaleString('en-US')} {data.total === 1 ? 'film' : 'films'}
                {data.pages > 1 && ` · page ${data.page.toLocaleString('en-US')} of ${data.pages.toLocaleString('en-US')}`}
              </p>
              <ul className={cn('grid gap-4 transition-opacity', view === 'list' ? 'gap-1' : GRID[view],
                movies.isPlaceholderData && 'opacity-60')} aria-label="Films">
                {data.items.map((film, i) => (
                  <li key={film.id}>
                    {view === 'list' ? <MovieListItem film={film} eager={i < EAGER} />
                      : <MovieCard film={film} showRevenue={state.sort === 'revenue'} eager={i < EAGER} />}
                  </li>
                ))}
              </ul>
              <Pager page={data.page} pages={data.pages} hrefFor={hrefFor} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
