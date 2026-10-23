import { useEffect, useState } from 'react'

/** True once `pending` has lasted `ms` (the free host may be waking up); false again as soon as it ends. */
export function useSlow(pending: boolean, ms = 3000) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!pending) return
    const timer = setTimeout(() => setSlow(true), ms)
    return () => {
      clearTimeout(timer)
      setSlow(false)
    }
  }, [pending, ms])
  return pending && slow
}
