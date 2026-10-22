// Pages that later days fill in: the results page (Day 11) and the film pages (Day 12).
import { useParams } from 'react-router'

import PageHeading from '@/pages/PageHeading'

export function PredictResult() {
  return <PageHeading title="Your prediction">The results page comes here on Day 11.</PageHeading>
}

export function Movies() {
  return <PageHeading title="Browse films">Search and browse comes here on Day 12.</PageHeading>
}

export function MovieDetail() {
  const { id } = useParams()
  return <PageHeading title="Film">Film {id}: the detail page comes here on Day 12.</PageHeading>
}
