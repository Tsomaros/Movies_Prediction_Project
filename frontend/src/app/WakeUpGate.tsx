// The wake-up screen. Render's free plan stops the server after 15 idle minutes and the first request then takes up to a
// minute. The app renders at once (waiting for the answer would add a round trip to every page load); on load we ask
// /api/v1/health, and if it hasn't answered OK within 2 s a full-screen notice covers the page. It asks again every 3 s
// (a new attempt cancels the one still pending) and goes away when the server is up. Fast answers never show it.
// It covers SlowNotice, which says the same for one slow request: the page behind is not usable yet anyway.
import { Loader2Icon } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'

import { useReducedMotion } from '@/lib/useReducedMotion'

const HEALTH = '/api/v1/health'
const SHOW_AFTER_MS = 2000
const RETRY_MS = 3000

export default function WakeUpGate({ children }: { children: ReactNode }) {
  const [waking, setWaking] = useState(false)
  const still = useReducedMotion()

  useEffect(() => {
    let done = false
    let pending: AbortController | undefined
    const check = async () => {
      pending?.abort()
      const own = (pending = new AbortController())
      try {
        const res = await fetch(HEALTH, { signal: own.signal, cache: 'no-store' })
        if (!res.ok || own.signal.aborted) return
        done = true
        clearInterval(retry)
        clearTimeout(show)
        pending = undefined
        setWaking(false)
      } catch {
        // offline, server down or this attempt replaced: the next one runs in 3 s
      }
    }
    const show = setTimeout(() => { if (!done) setWaking(true) }, SHOW_AFTER_MS)
    const retry = setInterval(check, RETRY_MS)
    void check()
    return () => {
      done = true
      clearTimeout(show)
      clearInterval(retry)
      pending?.abort()
    }
  }, [])

  return (
    <>
      {children}
      {waking && (
        <div role="status" aria-live="polite" data-testid="wake-up"
          className="bg-background fixed inset-0 z-[100] flex flex-col items-center justify-center gap-4 p-6 text-center">
          <Loader2Icon className={still ? 'size-8' : 'size-8 animate-spin'} aria-hidden />
          <p className="text-lg font-medium">Waking up the server…</p>
          <p className="text-muted-foreground max-w-md text-sm">
            Free hosting sleeps when idle; this can take up to a minute.
          </p>
        </div>
      )}
    </>
  )
}
