// Numbered pages: first, last, the current one with its neighbours, and "…" for the gaps. Each is a link, so
// the page is in the URL and the browser's back button works.
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { Link } from 'react-router'

import { cn } from '@/lib/utils'
import { pageNumbers } from '@/movies/browse'

const BOX = 'inline-flex h-9 min-w-9 items-center justify-center rounded-md px-2 text-sm tabular-nums'

export function Pager({ page, pages, hrefFor }: { page: number; pages: number; hrefFor: (page: number) => string }) {
  if (pages <= 1) return null
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center justify-center gap-1">
      {page > 1 ? (
        <Link to={hrefFor(page - 1)} className={cn(BOX, 'hover:bg-accent')} aria-label="Previous page"><ChevronLeftIcon className="size-4" /></Link>
      ) : <span className={cn(BOX, 'text-muted-foreground/50')} aria-hidden><ChevronLeftIcon className="size-4" /></span>}
      {pageNumbers(page, pages).map((p, i) => p === null ? (
        <span key={`gap-${i}`} className={cn(BOX, 'text-muted-foreground')} aria-hidden>…</span>
      ) : (
        <Link key={p} to={hrefFor(p)} aria-current={p === page ? 'page' : undefined} aria-label={`Page ${p}`}
          className={cn(BOX, p === page ? 'bg-primary text-primary-foreground' : 'hover:bg-accent')}>
          {p.toLocaleString('en-US')}
        </Link>
      ))}
      {page < pages ? (
        <Link to={hrefFor(page + 1)} className={cn(BOX, 'hover:bg-accent')} aria-label="Next page"><ChevronRightIcon className="size-4" /></Link>
      ) : <span className={cn(BOX, 'text-muted-foreground/50')} aria-hidden><ChevronRightIcon className="size-4" /></span>}
    </nav>
  )
}
