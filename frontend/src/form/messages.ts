// react-hook-form error objects -> the text shown under a field.

/** The message of a field or, for a list, of its first item with one (react-hook-form nests item errors). */
export function messageOf(error: unknown): string | undefined {
  if (!error || typeof error !== 'object') return undefined
  const e = error as { message?: unknown; root?: { message?: unknown } }
  if (typeof e.message === 'string' && e.message) return e.message
  if (typeof e.root?.message === 'string') return e.root.message
  if (Array.isArray(error)) for (const item of error) { const m = messageOf(item); if (m) return m }
  return undefined
}
