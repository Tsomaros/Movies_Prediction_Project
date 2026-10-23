// Text for people and facts on the film pages.
//
//   initials(name)        -> "Robert Downey Jr." -> "RD", "Zendaya" -> "Z"
//   nameHue(name)         -> a hue 0-359 from the name, so a person's avatar has the same colour on every page
//   runtimeText(minutes)  -> 149 -> "2 h 29 min", 90 -> "1 h 30 min", 45 -> "45 min"
//   crewByJob(crew, jobs) -> [{job, names}] in the order of `jobs`, each name once
//   votes(n)              -> 1 -> "1 vote", 1203 -> "1,203 votes"

const SUFFIXES = new Set(['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'])

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(w => w && !SUFFIXES.has(w.toLowerCase()))
  if (words.length === 0) return '?'
  const first = [...words[0]][0] ?? ''
  const last = words.length > 1 ? [...words[words.length - 1]][0] ?? '' : ''
  return (first + last).toUpperCase()
}

export function nameHue(name: string): number {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)!) % 360
  return h
}

export function runtimeText(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h === 0 ? `${m} min` : m === 0 ? `${h} h` : `${h} h ${m} min`
}

export function crewByJob(crew: { name?: string | null; job: string }[], jobs: string[]) {
  return jobs.map(job => ({
    job,
    names: [...new Set(crew.filter(c => c.job === job && c.name).map(c => c.name!))],
  })).filter(g => g.names.length > 0)
}

export const votes = (n: number) => `${n.toLocaleString('en-US')} ${n === 1 ? 'vote' : 'votes'}`
