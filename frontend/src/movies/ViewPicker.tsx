// The picker for the grid size or list view of a page of films (/browse, /my-movies); GRID is in browse.ts.
import { LayoutGridIcon, ListIcon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { type View, VIEWS } from '@/movies/browse'

const VIEW_LABELS: Record<View, string> = { small: 'Small posters', medium: 'Medium posters', large: 'Large posters', list: 'List' }

export function ViewPicker({ view, onChange }: { view: View; onChange: (v: View) => void }) {
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
