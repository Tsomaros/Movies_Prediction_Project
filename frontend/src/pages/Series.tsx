// /series: not built yet. The series collage, blurred, behind a short "coming soon" card.
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

export default function Series() {
  return (
    <section className="relative isolate flex flex-1 items-center justify-center overflow-hidden bg-neutral-900 px-4 py-16">
      <title>Series · Movie Prediction</title>
      <img src="/collages/series.webp" alt="" width={1200} height={1000}
        className="absolute inset-0 -z-10 size-full scale-110 object-cover blur-md" />
      <div aria-hidden className="absolute inset-0 -z-10 bg-black/60" />
      <div className="bg-card text-card-foreground grid max-w-md justify-items-start gap-3 rounded-lg border p-6 shadow-lg sm:p-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Series: coming soon</h1>
        <p className="text-muted-foreground">
          Predictions for TV series are on the way. Until then, browse the films or plan one of your own.
        </p>
        <Button asChild><Link to="/movies">Browse movies</Link></Button>
      </div>
    </section>
  )
}
