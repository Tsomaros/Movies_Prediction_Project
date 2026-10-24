// The reveal: the shuffle's posters flick past for about a second, slowing down, then the pick settles (the
// children). With "reduce motion" on, or nothing to shuffle, the pick shows at once. Only the pick is announced:
// the flicking posters are hidden from screen readers. Every poster is loaded up front and stacked, so a frame
// never waits for its image.
import { useEffect, useState, type ReactNode } from 'react'

import type { RandomPick } from '@/api/client'
import { useReducedMotion } from '@/lib/useReducedMotion'
import { cn } from '@/lib/utils'

const FRAME_MS = [60, 70, 85, 100, 120, 145, 175, 210] as const // about 1 s in all

export function Reveal({ shuffle, children }: { shuffle: RandomPick['shuffle']; children: ReactNode }) {
  const still = useReducedMotion()
  const [frame, setFrame] = useState(0)
  const frames = still ? 0 : Math.min(shuffle.length, FRAME_MS.length)
  useEffect(() => {
    let at = 0
    const timers = FRAME_MS.slice(0, frames).map((ms, i) => {
      at += ms
      return setTimeout(() => setFrame(i + 1), at)
    })
    return () => timers.forEach(clearTimeout)
  }, [frames])
  if (frame >= frames) return children
  return (
    <div className="grid justify-items-center gap-2 py-2" data-testid="reveal">
      <p className="sr-only" role="status">Picking a film…</p>
      <div aria-hidden className="relative aspect-[2/3] w-36 overflow-hidden rounded-md bg-muted shadow">
        {shuffle.slice(0, frames).map((p, i) => (
          <img key={p.small} src={p.small} alt="" decoding="async"
            className={cn('absolute inset-0 size-full object-cover', i === frame ? 'opacity-100' : 'opacity-0')} />
        ))}
      </div>
    </div>
  )
}
