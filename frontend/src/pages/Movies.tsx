// /movies: the live New Arrivals and Coming soon rows (V1.2), then the curated rows (src/movies/rows.ts), each with "See all" on /browse. Search and filters live on
// /browse; a link from before the split (/movies?q=…&genre=…) is sent on there with the same parameters.
import { Navigate, useSearchParams } from 'react-router'

import { CuratedRow } from '@/movies/CuratedRow'
import { LiveRows } from '@/movies/LiveRows'
import { BROWSE_PARAMS } from '@/movies/browse'
import { ROWS } from '@/movies/rows'
import PageHeading from '@/pages/PageHeading'

export default function Movies() {
  const [params] = useSearchParams()
  if (BROWSE_PARAMS.some(k => params.has(k))) return <Navigate replace to={`/browse?${params}`} />
  return (
    <div className="grid gap-10">
      <PageHeading title="Movies">Curated picks from 79,000 films, 1960 to 2025. "See all" opens the full list on Browse.</PageHeading>
      <div className="-mt-6 grid gap-10">
        <LiveRows />
        {ROWS.map((row, i) => <CuratedRow key={row.key} row={row} first={i === 0} />)}
      </div>
    </div>
  )
}
