import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { CuratedRow } from '@/movies/CuratedRow'
import { ROWS } from '@/movies/rows'

const POINTS = [
  { title: 'Budget, revenue and audience score', text: 'Each as a range: low, middle and high, right about 8 times in 10.' },
  { title: 'Why', text: 'The main reasons behind each estimate, in plain words.' },
  { title: 'Films like yours', text: 'Five past films with their real budget, revenue and score.' },
]

export default function Home() {
  return (
    <section>
      <title>Movie Prediction</title>
      <div className="max-w-2xl py-6 sm:py-12">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">How might your film do?</h1>
        <p className="text-muted-foreground mt-4 text-lg">
          Describe a planned film and see what 79,000 films from 1960 to 2025 suggest about its budget, box office
          and audience score.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg"><Link to="/predict">Plan a film</Link></Button>
          <Button asChild size="lg" variant="outline"><Link to="/movies">Browse films</Link></Button>
        </div>
      </div>
      <ul className="grid gap-4 sm:grid-cols-3">
        {POINTS.map(p => (
          <li key={p.title} className="rounded-lg border p-4">
            <h2 className="font-medium">{p.title}</h2>
            <p className="text-muted-foreground mt-1 text-sm">{p.text}</p>
          </li>
        ))}
      </ul>
      <div className="mt-12 grid gap-10">
        {ROWS.map(row => <CuratedRow key={row.key} row={row} />)}
      </div>
    </section>
  )
}
