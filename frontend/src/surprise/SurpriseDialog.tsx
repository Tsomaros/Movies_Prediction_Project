// The "Surprise me" dialog (a bottom sheet on phones), loaded on the first click of the header's button
// (SurpriseButton.tsx, which keeps the state). Pick a source (anything you haven't watched, or your watchlist),
// optionally open the filters, and spin: the posters shuffle, then one film settles.
import { DicesIcon, SlidersHorizontalIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { Genre, RandomPick } from '@/api/client'
import { useMetaOptions } from '@/api/hooks'
import { useMe } from '@/auth/session'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { codeName } from '@/form/format'
import { useMediaQuery } from '@/lib/useReducedMotion'
import { cn } from '@/lib/utils'
import { FilterSelect } from '@/movies/Filters'
import type { Surprise } from '@/surprise/hooks'
import { PickCard } from '@/surprise/PickCard'
import { activeFilters, DECADES, NO_FILTERS, RUNTIMES, type Source } from '@/surprise/prefs'
import { Reveal } from '@/surprise/Reveal'

const TITLE = 'Surprise me'
const DESCRIPTION = 'One random film, picked for you.'
const SOURCES: { value: Source; label: string }[] = [
  { value: 'all', label: "Anything I haven't seen" },
  { value: 'watchlist', label: 'From my watchlist' },
]

export default function SurpriseDialog({ open, onOpenChange, surprise }: {
  open: boolean; onOpenChange: (open: boolean) => void; surprise: Surprise
}) {
  const wide = useMediaQuery('(min-width: 640px)')
  const body = <SurprisePanel surprise={surprise} onClose={() => onOpenChange(false)} />
  return wide ? (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{TITLE}</DialogTitle>
          <DialogDescription>{DESCRIPTION}</DialogDescription>
        </DialogHeader>
        {body}
      </DialogContent>
    </Dialog>
  ) : (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[90dvh] overflow-y-auto rounded-t-xl p-4">
        <SheetHeader className="p-0">
          <SheetTitle>{TITLE}</SheetTitle>
          <SheetDescription>{DESCRIPTION}</SheetDescription>
        </SheetHeader>
        {body}
      </SheetContent>
    </Sheet>
  )
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-sm font-medium">{label}</label>
      {children}
    </div>
  )
}

function SurprisePanel({ surprise, onClose }: { surprise: Surprise; onClose: () => void }) {
  const { prefs, setPrefs, pick, spinning, spin, startOver } = surprise
  const { user } = useMe()
  const { data: options } = useMetaOptions()
  const count = activeFilters(prefs)
  const [filtersOpen, setFiltersOpen] = useState(count > 0)
  return (
    <div className="grid gap-4">
      <div className="grid gap-1.5">
        <div role="radiogroup" aria-label="Pick from" className="bg-muted grid grid-cols-2 rounded-md p-0.5">
          {SOURCES.map(s => (
            <button key={s.value} type="button" role="radio" aria-checked={prefs.source === s.value}
              onClick={() => setPrefs({ source: s.value })}
              className={cn('rounded px-2 py-1.5 text-sm',
                prefs.source === s.value ? 'bg-background font-medium shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
              {s.label}
            </button>
          ))}
        </div>
        {prefs.source === 'watchlist' && !user && (
          <p className="text-muted-foreground text-xs">Your watchlist needs a login. The demo account takes one click.</p>
        )}
      </div>

      <div className="grid gap-3">
        <Button variant="outline" size="sm" className="justify-self-start" aria-expanded={filtersOpen}
          aria-controls="surprise-filters" onClick={() => setFiltersOpen(o => !o)}>
          <SlidersHorizontalIcon aria-hidden />
          Filters{count > 0 && ` (${count})`}
        </Button>
        {filtersOpen && (
          <div id="surprise-filters" role="group" aria-label="Filters" className="grid grid-cols-2 gap-3">
            <Field id="s-genre" label="Genre">
              <FilterSelect id="s-genre" value={prefs.genre} any="Any genre" onChange={g => setPrefs({ genre: g as Genre | null })}
                choices={(options?.genres ?? []).map(g => ({ value: g, label: g }))} />
            </Field>
            <Field id="s-decade" label="Decade">
              <FilterSelect id="s-decade" value={prefs.decade === null ? null : String(prefs.decade)} any="Any decade"
                onChange={d => setPrefs({ decade: d === null ? null : Number(d) })}
                choices={DECADES.map(d => ({ value: String(d), label: `${d}s` }))} />
            </Field>
            <Field id="s-lang" label="Language">
              <FilterSelect id="s-lang" value={prefs.language} any="Any language" onChange={language => setPrefs({ language })}
                choices={(options?.languages ?? []).map(l => ({ value: l.code, label: codeName('language', l.code) }))} />
            </Field>
            <Field id="s-runtime" label="Runtime">
              <FilterSelect id="s-runtime" value={prefs.maxRuntime === null ? null : String(prefs.maxRuntime)} any="Any length"
                onChange={m => setPrefs({ maxRuntime: m === null ? null : Number(m) })}
                choices={RUNTIMES.map(m => ({ value: String(m), label: `Up to ${m} min` }))} />
            </Field>
            {prefs.source === 'all' && (
              <label className="col-span-2 flex items-start gap-2 text-sm">
                <input type="checkbox" checked={prefs.gems} onChange={e => setPrefs({ gems: e.target.checked })}
                  className="accent-primary mt-0.5 size-4" />
                <span>
                  Include hidden gems
                  <span className="text-muted-foreground block text-xs">Also less-known films: under 200 votes or a score under 6.0.</span>
                </span>
              </label>
            )}
          </div>
        )}
      </div>

      <div aria-live="polite" className="empty:hidden">
        {pick?.movie ? (
          <Reveal key={pick.movie.id} shuffle={pick.shuffle}>
            <PickCard movie={pick.movie} pool={pick.pool} source={prefs.source} onOpen={onClose} />
          </Reveal>
        ) : pick?.reason ? (
          <EmptyState reason={pick.reason} onClose={onClose} onStartOver={startOver}
            onClearFilters={() => setPrefs({ ...NO_FILTERS, gems: false })} />
        ) : null}
      </div>

      <Button onClick={spin} disabled={spinning} className="w-full">
        <DicesIcon aria-hidden />
        {spinning ? 'Spinning…' : pick?.movie ? 'Spin again' : 'Spin'}
      </Button>
    </div>
  )
}

const EMPTY = {
  watchlist_empty: ['Add films first', 'Your watchlist is empty. Add films from Browse, then spin from your list.'],
  no_match: ['Loosen a filter', 'No film matches all of these filters.'],
  all_seen: ["You've seen them all", 'Every film that matches is watched or was already picked. Nice going!'],
} as const

function EmptyState({ reason, onClose, onStartOver, onClearFilters }: {
  reason: NonNullable<RandomPick['reason']>; onClose: () => void; onStartOver: () => void; onClearFilters: () => void
}) {
  const [title, text] = EMPTY[reason]
  return (
    <div className="bg-muted/50 grid justify-items-start gap-2 rounded-md p-4" data-testid="surprise-empty">
      <h3 className="font-semibold">{title}</h3>
      <p className="text-muted-foreground text-sm">{text}</p>
      {reason === 'watchlist_empty' && (
        <Button asChild size="sm" variant="outline"><Link to="/browse" onClick={onClose}>Browse films</Link></Button>
      )}
      {reason === 'no_match' && <Button size="sm" variant="outline" onClick={onClearFilters}>Clear filters</Button>}
      {reason === 'all_seen' && <Button size="sm" variant="outline" onClick={onStartOver}>Start over</Button>}
    </div>
  )
}
