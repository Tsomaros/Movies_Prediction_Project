// The notice for a request that takes more than 3 s: on free hosting the server sleeps when idle and needs up to a
// minute to wake up, so a slow first answer is expected, not broken.
import { Loader2Icon } from 'lucide-react'

import { useSlow } from '@/lib/useSlow'

export const WAKING_UP = 'Waking up the server, this can take up to a minute on free hosting.'

export function SlowNotice({ pending }: { pending: boolean }) {
  const slow = useSlow(pending)
  if (!slow) return null
  return (
    <p role="status" data-testid="slow-notice" className="text-muted-foreground flex items-center gap-2 text-sm">
      <Loader2Icon className="size-4 animate-spin" aria-hidden /> {WAKING_UP}
    </p>
  )
}
