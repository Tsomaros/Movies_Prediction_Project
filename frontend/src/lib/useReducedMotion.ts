import { useMemo, useSyncExternalStore } from 'react'

function subscribe(query: string) {
  return (onChange: () => void) => {
    const media = window.matchMedia(query)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }
}

/** True while the media query matches; follows it when it changes (a resize, a system setting). */
export function useMediaQuery(query: string): boolean {
  const listen = useMemo(() => subscribe(query), [query])
  return useSyncExternalStore(listen, () => window.matchMedia(query).matches, () => false)
}

/** True when the visitor asked their system for less motion; follows the setting if it changes. */
export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}
