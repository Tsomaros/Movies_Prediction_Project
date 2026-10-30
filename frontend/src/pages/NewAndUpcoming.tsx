// /new-and-upcoming (V1.2): the live films in two tabs, Out now (released in the last 14 days) and Coming soon (the
// next 60), kept in ?tab= (an unknown value is corrected to Out now) with the page in ?page=. The same poster grid
// and size picker as /browse, paged on the client, 24 a page (a list has at most 100 films). The data is the 6-hour
// TMDB cache, so the heading says when it was updated; if it can't load there is a Retry.
import { Link, Navigate, useSearchParams } from 'react-router'

import { useNewAndUpcoming } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { updatedAgo } from '@/lib/live'
import { cn } from '@/lib/utils'
import { GRID, loadView, PAGE_SIZE, saveView, type View } from '@/movies/browse'
import { LiveMovieCard } from '@/movies/LiveMovieCard'
import { Pager } from '@/movies/Pager'
import { ViewPicker } from '@/movies/ViewPicker'
import PageHeading from '@/pages/PageHeading'
import { useState } from 'react'

const TABS = [{ value: 'out-now', label: 'Out now', key: 'new' }, { value: 'coming-soon', label: 'Coming soon', key: 'upcoming' }] as const

export default function NewAndUpcoming() {
  const [params, setParams] = useSearchParams()
  const live = useNewAndUpcoming()
  const [stored, setView] = useState<View>(loadView)
  const view: Exclude<View, 'list'> = stored === 'list' ? 'medium' : stored // the grid only: a list view makes no sense for 24 posters
  const tab = TABS.find(t => t.value === params.get('tab'))
  if (!tab) return <Navigate replace to={`/new-and-upcoming?${new URLSearchParams({ tab: 'out-now' })}`} />
  const films = live.data?.[tab.key] ?? []
  const pages = Math.max(1, Math.ceil(films.length / PAGE_SIZE))
  const page = Math.min(Math.max(1, Number(params.get('page')) || 1), pages)
  const shown = films.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hrefFor = (p: number) => `/new-and-upcoming?${new URLSearchParams({ tab: tab.value, ...(p > 1 ? { page: String(p) } : {}) })}`
  const chooseView = (v: View) => { setView(v); saveView(v) }

  return (
    <div className="grid gap-6">
      <PageHeading title="New & upcoming">
        {live.data?.fetched_at ? updatedAgo(live.data.fetched_at) : 'Films that came out in the last 14 days and the ones coming in the next 60.'}
      </PageHeading>

      <div className="-mt-2 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={tab.value} onValueChange={v => setParams({ tab: v }, { preventScrollReset: true })}>
          <TabsList>
            {TABS.map(t => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
          </TabsList>
        </Tabs>
        <ViewPicker view={view} onChange={chooseView} />
      </div>

      <SlowNotice pending={live.isPending} />
      {live.isPending && (
        <div className={cn('grid gap-4', GRID[view])} aria-busy="true">
          <span className="sr-only">Loading films…</span>
          {Array.from({ length: 12 }, (_, i) => <Skeleton key={i} className="aspect-[2/3]" />)}
        </div>
      )}
      {(live.isError || (live.data && live.data.new.length + live.data.upcoming.length === 0)) && (
        <div role="alert" className="grid justify-items-start gap-3 rounded-lg border p-6">
          <p>We can't load new releases right now.</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" onClick={() => live.refetch()}>Retry</Button>
            <Link to="/browse" className="text-primary text-sm underline">Back to browse</Link>
          </div>
        </div>
      )}
      {live.data && live.data.new.length + live.data.upcoming.length > 0 && shown.length === 0 && (
        <p className="text-muted-foreground">Nothing in this list right now.</p>
      )}
      {shown.length > 0 && (
        <>
          <ul className={cn('grid gap-4', GRID[view])} aria-label={tab.label}>
            {shown.map((film, i) => <li key={film.tmdb_id}><LiveMovieCard film={film} eager={i < 6} /></li>)}
          </ul>
          <Pager page={page} pages={pages} hrefFor={hrefFor} />
        </>
      )}
    </div>
  )
}
