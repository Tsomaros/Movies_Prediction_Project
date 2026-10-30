// "New Arrivals" and "Coming soon" (V1.2): the two live rows above /movies and the default view of /browse. While the
// live request is on its way a fixed-height skeleton holds the space; on an error, or with nothing to show,
// nothing is rendered (an empty list hides only its own row), so the rest of the page is never affected.
import { useNewAndUpcoming } from '@/api/hooks'
import { LiveRow, LiveRowSkeleton } from '@/movies/LiveRow'

export function LiveRows() {
  const live = useNewAndUpcoming()
  if (live.isPending) return <LiveRowSkeleton />
  if (!live.data) return null
  const { new: out, upcoming } = live.data
  if (out.length === 0 && upcoming.length === 0) return null
  return (
    <div className="grid gap-8" data-testid="live-rows">
      {out.length > 0 && <LiveRow title="New Arrivals" films={out} seeAllHref="/new-and-upcoming?tab=out-now" />}
      {upcoming.length > 0 && <LiveRow title="Coming soon" films={upcoming} seeAllHref="/new-and-upcoming?tab=coming-soon" variant="small" />}
    </div>
  )
}
