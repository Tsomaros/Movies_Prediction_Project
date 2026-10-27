// Error reports to Sentry (Day 15), only when the build had VITE_SENTRY_DSN (the production image). The SDK is
// loaded in the background, in its own chunk, so the start page's bundle stays as small as before. Errors only:
// no tracing, no session replay, no personal data (Sentry's default).
type Sentry = typeof import('@/lib/sentry')

let sentry: Promise<Sentry> | null = null

export function startMonitoring(dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined) {
  if (!dsn || sentry) return
  sentry = import('@/lib/sentry').then((S) => {
    S.init({ dsn, release: import.meta.env.VITE_APP_RELEASE as string | undefined })
    return S
  })
}

// A crash caught by a route's error page never reaches the global handlers, so the page reports it.
export function reportError(error: unknown) {
  void sentry?.then((S) => S.captureException(error))
}
