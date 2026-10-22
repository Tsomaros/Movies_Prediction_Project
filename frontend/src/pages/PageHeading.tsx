// A page's title: the visible heading and the browser tab's title (React 19 hoists <title> into <head>).
import type { ReactNode } from 'react'

export default function PageHeading({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6">
      <title>{`${title} · Movie Prediction`}</title>
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {children && <p className="text-muted-foreground mt-2 max-w-prose">{children}</p>}
    </div>
  )
}
