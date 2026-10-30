// The person's biography as plain text paragraphs; a long one starts clamped to 4 lines with "Read more".
import { useState } from 'react'

import { cn } from '@/lib/utils'

const LONG_BIO = 600 // characters

export function Biography({ text }: { text: string }) {
  const long = text.length > LONG_BIO
  const [open, setOpen] = useState(!long)
  const paragraphs = text.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
  return (
    <div className="grid justify-items-start gap-1">
      <div className={cn('grid max-w-prose gap-2', !open && 'line-clamp-4')} data-testid="biography">
        {paragraphs.map((p, i) => <p key={i}>{p}</p>)}
      </div>
      {long && (
        <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} className="text-primary text-sm underline">
          {open ? 'Show less' : 'Read more'}
        </button>
      )}
    </div>
  )
}
