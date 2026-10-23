// Shared handling of API errors, so every page reacts the same way.
//
//   notifyError(error, retry?)                    -> a toast for 429 ("try again in a minute"), network and server
//                                                    errors (with a Retry button when `retry` is given); returns
//                                                    false for a 422 or a non-API error, which the caller shows
//   applyFieldErrors(error, setError, toField?)   -> puts a 422's messages on the form's fields; returns the
//                                                    messages no field took (shown above the form)
import { toast } from 'sonner'

import { ApiError } from '@/api/client'

export const RATE_LIMITED = "You're going a bit fast. Try again in a minute."

export function notifyError(error: unknown, retry?: () => void): boolean {
  if (!(error instanceof ApiError) || error.kind === 'validation') return false
  const action = retry ? { label: 'Retry', onClick: retry } : undefined
  if (error.kind === 'rate_limited') {
    const wait = error.retryAfter && error.retryAfter > 60 ? `in ${Math.ceil(error.retryAfter / 60)} minutes` : 'in a minute'
    toast.warning(RATE_LIMITED.replace('in a minute', wait), { id: 'rate-limited' })
  } else if (error.kind === 'network') {
    toast.error(error.message, { id: 'network', action })
  } else {
    toast.error(error.message, { id: `api-${error.kind}`, action })
  }
  return true
}

type SetError = (name: never, error: { type: string; message: string }, options?: { shouldFocus?: boolean }) => void

/** `toField` turns an API path ("actors.2") into the form's field name, or null when the form has no such
 *  field; by default the names are the same. The first field with an error gets the focus. */
export function applyFieldErrors(error: unknown, setError: SetError,
  toField: (path: string) => string | null = path => path): string[] {
  if (!(error instanceof ApiError) || error.kind !== 'validation') return []
  const leftover: string[] = []
  let first = true
  for (const [path, message] of Object.entries(error.fieldErrors)) {
    const field = toField(path)
    if (field === null) {
      leftover.push(`${path}: ${message}`)
      continue
    }
    setError(field as never, { type: 'server', message }, { shouldFocus: first })
    first = false
  }
  if (Object.keys(error.fieldErrors).length === 0) leftover.push(error.message)
  return leftover
}
