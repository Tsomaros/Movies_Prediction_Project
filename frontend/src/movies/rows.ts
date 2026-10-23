// The home page's curated rows: one entry per row, in order. Each row is a browse query (src/movies/browse.ts),
// so "See all" opens the same films on /movies, and changing a row is a one-line edit here.
//
//   key        -> React key and test id (row-<key>)
//   title      -> the row's heading
//   filters    -> the browse state the row shows (sort, years, score...)
//   showRevenue -> print each film's box office under it (for the box-office row)
import type { BrowseState } from '@/movies/browse'

export type CuratedRow = { key: string; title: string; filters: Partial<BrowseState>; showRevenue?: boolean }

export const ROW_SIZE = 12

export const ROWS: CuratedRow[] = [
  { key: 'popular', title: 'Most popular', filters: { sort: 'popularity' } },
  { key: 'top-rated', title: 'Top rated (50+ votes)', filters: { sort: 'score' } },
  { key: '1990s', title: 'From the 1990s', filters: { yearFrom: 1990, yearTo: 1999, sort: 'popularity' } },
  { key: 'box-office', title: 'Biggest box office (2025 $)', filters: { sort: 'revenue' }, showRevenue: true },
]
