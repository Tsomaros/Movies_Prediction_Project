// Text for the form's inputs: names of ISO codes, film counts, months and money.
import type { NameKind } from '@/api/client'

export type CodeKind = 'language' | 'region'

const NAMES: Partial<Record<CodeKind, Intl.DisplayNames>> = {}

/** "fr" -> "French", "GB" -> "United Kingdom"; TMDB's own codes ("xx", "cn") get their names by hand. */
export function codeName(kind: CodeKind, code: string): string {
  if (kind === 'language' && code === 'xx') return 'No language'
  if (kind === 'language' && code === 'cn') return 'Cantonese'
  try {
    NAMES[kind] ??= new Intl.DisplayNames(['en'], { type: kind, fallback: 'code' })
    return NAMES[kind]!.of(kind === 'region' ? code.toUpperCase() : code) ?? code
  } catch {
    return code
  }
}

export const formatFilms = (n: number) => `${n.toLocaleString('en-US')} ${n === 1 ? 'film' : 'films'}`

/** How many films a suggestion has in our data, in its role: "12 directed", "1 film". */
export function filmCount(kind: NameKind, n: number) {
  return kind === 'director' ? `${n} directed` : formatFilms(n)
}

export const MONTHS = Array.from({ length: 12 }, (_, i) => new Date(2000, i, 1).toLocaleString('en-US', { month: 'long' }))

/** The budget box's text in millions -> whole dollars: "2.5" -> 2500000, "" or "." -> null */
export function toDollars(millions: string): number | null {
  const m = Number(millions)
  return millions.trim() === '' || !Number.isFinite(m) || millions.trim() === '.' ? null : Math.round(m * 1e6)
}

/** Whole dollars -> the budget box's text: 2500000 -> "2.5", 1000 -> "0.001" */
export const millionsText = (dollars: number | null) => (dollars === null ? '' : String(+(dollars / 1e6).toFixed(6)))

/** 12500000 -> "$12.5M" */
export function shortMoney(n: number) {
  if (n >= 1e9) return `$${+(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${+(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${+(n / 1e3).toFixed(0)}K`
  return `$${n}`
}
