// The stats strip under a person's name: films, genres, average score, box office and who they work with most.
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { money, points } from '@/result/format'

import { ROLE_TEXT, type Role } from './roles'

export function Stats({ role }: { role: Role }) {
  const s = role.stats
  const text = ROLE_TEXT[role.role]
  const chips: { key: string; content: ReactNode }[] = []
  if (s.film_count > 0) {
    const years = s.first_year == null ? '' : s.first_year === s.last_year ? ` · ${s.first_year}` : ` · ${s.first_year}–${s.last_year}`
    const films = `${s.film_count} ${s.film_count === 1 ? 'film' : 'films'}`
    chips.push({ key: 'films', content: `${text.verb ? `${text.verb} ${films}` : films}${years}` })
  }
  if (s.top_genres.length > 0) chips.push({ key: 'genres', content: `Mostly ${s.top_genres.map(g => g.name).join(', ')}` })
  if (s.avg_score) chips.push({ key: 'score', content: `Average score ${points(s.avg_score.value)} from ${s.avg_score.films} ${s.avg_score.films === 1 ? 'film' : 'films'}` })
  if (s.box_office_2025) {
    const b = s.box_office_2025
    chips.push({ key: 'money', content: `${money(b.total)} box office (2025 $) from ${b.films} of ${b.of} films` })
  }
  for (const [key, label, ref] of [['actor', text.cast, s.top_actor], ['director', 'Most often directed by', s.top_director]] as const) {
    if (ref) chips.push({ key, content: <>{label} <Link to={`/people/${ref.id}`} className="font-medium underline">{ref.name}</Link> ({ref.shared_films} films)</> })
  }
  if (chips.length === 0) return null
  return (
    <ul aria-label="Stats" className="flex flex-wrap gap-2">
      {chips.map(c => <li key={c.key} className="bg-secondary text-secondary-foreground rounded-full px-3 py-1 text-sm">{c.content}</li>)}
    </ul>
  )
}
