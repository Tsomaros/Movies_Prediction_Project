// /my-movies: the logged-in visitor's Watched, Plan to watch and Notes tabs, with their counts. Tab, sort and page
// are in the URL (src/me/myMovies.ts). The lists reuse the browse grid, its grid-size control and the pager; the
// Notes tab lists every note newest first with its film. Logged out, the page offers the demo login.
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { MyMovieList, NotePage } from '@/api/client'
import { SlowNotice } from '@/app/SlowNotice'
import { DemoLogin } from '@/auth/DemoLogin'
import { useMe } from '@/auth/session'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { GRID, loadView, saveView, type View } from '@/movies/browse'
import { FilterSelect } from '@/movies/Filters'
import { MovieCard, MovieListItem } from '@/movies/MovieCard'
import { Pager } from '@/movies/Pager'
import { Poster } from '@/movies/Poster'
import { ViewPicker } from '@/movies/ViewPicker'
import { noteDate, useAllNotes, useMyMovies } from '@/me/hooks'
import { readMyMovies, SORTS_FOR, TABS, writeMyMovies, type MyMoviesState, type Tab } from '@/me/myMovies'
import PageHeading from '@/pages/PageHeading'

const EMPTY_TEXT: Record<Tab, string> = {
  watched: 'No watched films yet. Mark a film as watched from its page or a poster in Browse.',
  plan_to_watch: 'Nothing on your watchlist yet. Add films you want to see from Browse.',
  notes: 'No notes yet. Write one on any film’s page.',
}

function Empty({ tab }: { tab: Tab }) {
  return (
    <div className="grid justify-items-start gap-3 rounded-lg border border-dashed p-6" data-testid="my-empty">
      <p>{EMPTY_TEXT[tab]}</p>
      <Button asChild variant="outline"><Link to="/browse">Browse films</Link></Button>
    </div>
  )
}

function Loading() {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4" aria-busy="true">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="aspect-[2/3]" />)}
    </div>
  )
}

function FilmList({ data, view, placeholder }: { data: MyMovieList; view: View; placeholder: boolean }) {
  return (
    <ul className={cn('grid gap-4 transition-opacity', view === 'list' ? 'gap-1' : GRID[view], placeholder && 'opacity-60')}
      aria-label="Films">
      {data.items.map(({ movie, entry }) => (
        <li key={movie.id}>
          {view === 'list' ? <MovieListItem film={movie} entry={entry} quick />
            : <MovieCard film={movie} entry={entry} quick />}
        </li>
      ))}
    </ul>
  )
}

function NoteList({ data }: { data: NotePage }) {
  return (
    <ul className="grid gap-3" aria-label="Notes, newest first">
      {data.items.map(n => (
        <li key={n.id} className="bg-card grid grid-cols-[3.5rem_1fr] gap-3 rounded-lg border p-3">
          {n.movie ? <Link to={`/movies/${n.movie.id}`}><Poster poster={n.movie.poster} title={n.movie.title} /></Link> : <span />}
          <div className="grid content-start gap-1">
            {n.movie
              ? <Link to={`/movies/${n.movie.id}`} className="font-medium hover:underline">{n.movie.title} <span className="text-muted-foreground font-normal">({n.movie.year ?? '?'})</span></Link>
              : <span className="text-muted-foreground">A film no longer in our data</span>}
            <p className="whitespace-pre-wrap break-words text-sm">{n.body}</p>
            <p className="text-muted-foreground text-xs">{noteDate(n.created_at)}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}

export default function MyMovies() {
  const me = useMe()
  const [params, setParams] = useSearchParams()
  const state = readMyMovies(params)
  const [view, setView] = useState<View>(loadView)
  const loggedIn = me.user !== null
  const lists = useMyMovies({ status: state.tab === 'notes' ? 'watched' : state.tab, sort: state.sort, page: state.page },
    loggedIn && state.tab !== 'notes')
  const notes = useAllNotes(state.page, loggedIn && state.tab === 'notes')
  const go = (next: MyMoviesState) => setParams(writeMyMovies(next))
  const hrefFor = (page: number) => `/my-movies?${writeMyMovies({ ...state, page })}`
  const current = state.tab === 'notes' ? notes : lists
  const counts = current.data?.counts

  if (me.isPending) return <Loading />
  if (!loggedIn) {
    return (
      <div className="grid gap-6">
        <PageHeading title="My movies">Your watched films, watchlist and notes.</PageHeading>
        <div className="bg-card grid max-w-sm gap-4 rounded-lg border p-5">
          <p className="text-sm">Log in to see your lists. The demo account comes with a few films already.</p>
          <DemoLogin onDone={() => {}} />
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <title>My movies · Movie Prediction</title>
      <PageHeading title="My movies">Your watched films, watchlist and private notes.</PageHeading>
      <Tabs value={state.tab} onValueChange={tab => go({ tab: tab as Tab, sort: 'added', page: 1 })} className="-mt-2 gap-3">
        <TabsList>
          {TABS.map(t => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
              {counts && <span className="text-muted-foreground tabular-nums">{counts[t.value]}</span>}
            </TabsTrigger>
          ))}
        </TabsList>
        {me.user?.is_demo && (
          <p className="text-muted-foreground text-xs">Demo data resets every night. Everyone using the demo account sees the same lists.</p>
        )}
        {TABS.map(t => (
          <TabsContent key={t.value} value={t.value} className="grid gap-4">
            {t.value !== 'notes' && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground" aria-hidden>Sort</span>
                <FilterSelect label="Sort by" value={state.sort} className="bg-card h-8 w-40" choices={SORTS_FOR(t.value)}
                  onChange={sort => go({ ...state, sort: (sort ?? 'added') as MyMoviesState['sort'], page: 1 })} />
                <div className="ml-auto"><ViewPicker view={view} onChange={v => { setView(v); saveView(v) }} /></div>
              </div>
            )}
            <SlowNotice pending={current.isPending} />
            {current.isPending && <Loading />}
            {current.isError && (
              <div role="alert" className="grid justify-items-start gap-3 rounded-lg border p-4">
                <p>Your {t.label.toLowerCase()} couldn't load: {current.error.message}</p>
                <Button variant="outline" onClick={() => current.refetch()}>Try again</Button>
              </div>
            )}
            {current.data && current.data.items.length === 0 && <Empty tab={t.value} />}
            {current.data && current.data.items.length > 0 && (
              <>
                {state.tab === 'notes' ? <NoteList data={notes.data!} />
                  : <FilmList data={lists.data!} view={view} placeholder={lists.isPlaceholderData} />}
                <Pager page={current.data.page} pages={current.data.pages} hrefFor={hrefFor} />
              </>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
