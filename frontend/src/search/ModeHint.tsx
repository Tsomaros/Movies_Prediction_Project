// "2 people found → See people": the way out of an empty search in the wrong mode, in the header's dropdown and
// on both results pages. It asks the other mode's total itself and shows nothing until that mode has hits.
import { ArrowRightIcon } from 'lucide-react'
import { Link } from 'react-router'

import { useOtherModeCount } from '@/api/hooks'
import { cn } from '@/lib/utils'
import { count, resultsUrl, type SearchMode } from '@/search/search'

export function ModeHint({ mode, q, onFollow, replace, className }: {
  mode: SearchMode; q: string; onFollow?: () => void; replace?: boolean; className?: string
}) {
  const other: SearchMode = mode === 'movies' ? 'people' : 'movies'
  const found = useOtherModeCount(mode, q, true).data ?? 0
  if (found === 0) return null
  return (
    <Link to={resultsUrl(other, q)} onClick={onFollow} replace={replace} data-testid="mode-hint"
      className={cn('text-primary inline-flex items-center gap-1 text-sm font-medium underline-offset-4 hover:underline', className)}>
      {count(found, other)} found <ArrowRightIcon className="size-3.5" aria-hidden /> See {other}
    </Link>
  )
}
