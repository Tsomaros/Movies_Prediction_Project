// /people?q=&role=&page=: the header search's people results (V1.1). Actors, directors and writers whose name
// matches q (any word starting with it, accents folded), 24 a page, with role chips (All · Actors · Directors ·
// Writers) and how many each would show; an empty chip is disabled. Everything is in the URL: an unknown role
// becomes All (the address is corrected in place), a new role goes back to page 1. With fewer than 2 letters the
// page asks for a name and puts the focus in the header's box; an empty search points to the films that match.
import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { PeopleSearchResult, SearchRole } from '@/api/client'
import { PEOPLE_PAGE, usePeopleSearchPage } from '@/api/hooks'
import { SlowNotice } from '@/app/SlowNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { initials, nameHue } from '@/movies/people'
import { Pager } from '@/movies/Pager'
import { ModeHint } from '@/search/ModeHint'
import { count, focusHeaderSearch, rolesLine, usableQuery } from '@/search/search'

const ROLES: { role: SearchRole; label: string }[] = [
  { role: 'all', label: 'All' }, { role: 'actor', label: 'Actors' }, { role: 'director', label: 'Directors' },
  { role: 'writer', label: 'Writers' },
]
const GRID = 'grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6'

function readRole(value: string | null): SearchRole | null {
  return ROLES.some(r => r.role === value) ? value as SearchRole : null
}

function PersonCard({ person }: { person: PeopleSearchResult }) {
  return (
    <Link to={`/people/${person.id}`} data-testid="person-card"
      className="group grid content-start gap-2 rounded-md focus-visible:outline-2 focus-visible:outline-ring">
      {person.thumb ? (
        <img src={person.thumb} alt="" loading="lazy" decoding="async" className="bg-muted aspect-[2/3] w-full rounded-md object-cover" />
      ) : (
        <span aria-hidden className="inline-flex aspect-[2/3] w-full items-center justify-center rounded-md text-2xl font-semibold text-white"
          style={{ backgroundColor: `hsl(${nameHue(person.name)} 45% 38%)` }}>
          {initials(person.name)}
        </span>
      )}
      <span className="grid gap-0.5">
        <span className="line-clamp-2 text-sm font-medium leading-tight group-hover:underline">{person.name}</span>
        <span className="text-muted-foreground text-xs">{rolesLine(person.roles)}</span>
        {person.known_for && (
          <span className="text-muted-foreground line-clamp-2 text-xs">
            Known for {person.known_for.title}{person.known_for.year ? ` (${person.known_for.year})` : ''}
          </span>
        )}
      </span>
    </Link>
  )
}

export default function PeopleSearch() {
  const [params, setParams] = useSearchParams()
  const q = (params.get('q') ?? '').slice(0, 100)
  const rawRole = params.get('role')
  const role = readRole(rawRole) ?? 'all'
  const page = Math.max(1, Math.min(10_000, Number.parseInt(params.get('page') ?? '1', 10) || 1))
  const term = usableQuery(q)
  const search = usePeopleSearchPage(q, role, page)
  const data = search.data

  useEffect(() => { // an unknown role is All: correct the address in place
    if (rawRole !== null && (readRole(rawRole) === null || rawRole === 'all')) {
      const next = new URLSearchParams(params)
      next.delete('role')
      setParams(next, { replace: true })
    }
  }, [rawRole, params, setParams])
  useEffect(() => { if (term === null) focusHeaderSearch() }, [term])

  const href = (patch: { role?: SearchRole; page?: number }) => {
    const next = new URLSearchParams()
    next.set('q', q)
    const r = patch.role ?? role
    if (r !== 'all') next.set('role', r)
    const p = patch.page ?? 1
    if (p > 1) next.set('page', String(p))
    return `/people?${next.toString().replace(/\+/g, '%20')}`
  }

  if (term === null) {
    return (
      <div className="grid gap-4">
        <title>People · Movie Prediction</title>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">People</h1>
        <p className="text-muted-foreground">Type a name in the search bar above.</p>
      </div>
    )
  }

  const pages = data ? Math.ceil(data.total / PEOPLE_PAGE) : 0
  return (
    <div className="grid gap-6">
      <title>{`People: ${q.trim()} · Movie Prediction`}</title>
      <div className="grid gap-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">People matching ‘{q.trim()}’</h1>
        {data && <p className="text-muted-foreground text-sm" aria-live="polite">{count(data.total, 'people')}</p>}
      </div>

      {data && (
        <ul aria-label="Roles" className="flex flex-wrap gap-2">
          {ROLES.map(r => {
            const n = data.role_counts[r.role]
            const current = r.role === role
            return (
              <li key={r.role}>
                <Button asChild={n > 0 && !current} variant={current ? 'default' : 'outline'} size="sm" disabled={n === 0 && !current}
                  aria-pressed={current}>
                  {n > 0 && !current ? <Link to={href({ role: r.role })}>{r.label} <span className="tabular-nums opacity-70">{n.toLocaleString('en-US')}</span></Link>
                    : <span>{r.label} <span className="tabular-nums opacity-70">{n.toLocaleString('en-US')}</span></span>}
                </Button>
              </li>
            )
          })}
        </ul>
      )}

      <SlowNotice pending={search.isPending} />
      {search.isPending && (
        <div className={GRID} aria-busy="true">
          <span className="sr-only">Loading people…</span>
          {Array.from({ length: 12 }, (_, i) => <Skeleton key={i} className="aspect-[2/3]" />)}
        </div>
      )}
      {search.isError && !data && (
        <div role="alert" className="grid justify-items-start gap-3 rounded-lg border p-4">
          <p>The people couldn't load: {search.error.message}</p>
          <Button variant="outline" onClick={() => search.refetch()}>Try again</Button>
        </div>
      )}
      {data && data.total === 0 && (
        <div className="grid justify-items-start gap-2 rounded-lg border p-6" data-testid="no-results">
          <p className="font-medium">No people match ‘{q.trim()}’.</p>
          <ModeHint mode="people" q={q.trim()} />
        </div>
      )}
      {data && data.total > 0 && data.results.length === 0 && (
        <div className="grid justify-items-start gap-2 rounded-lg border p-6">
          <p className="font-medium">This page doesn't exist</p>
          <Link to={href({ page: 1 })} className="text-primary underline">Back to page 1</Link>
        </div>
      )}
      {data && data.results.length > 0 && (
        <>
          <ul aria-label="People" className={cn(GRID, 'transition-opacity', search.isPlaceholderData && 'opacity-60')}>
            {data.results.map(p => <li key={p.id}><PersonCard person={p} /></li>)}
          </ul>
          <Pager page={page} pages={pages} hrefFor={p => href({ page: p })} />
        </>
      )}
    </div>
  )
}
