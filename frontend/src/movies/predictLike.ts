// "Predict a film like this": a film's page -> a creator form to start from. The one place that decides what
// carries over, so it is easy to change.
//
//   filmToForm(film, options, today?)  -> FormValues: genres, themes, runtime, language, US rating, the director
//                                         and the top-billed cast; the release date and everything else as a
//                                         fresh form has them (it is a new film, not a remake of this one)
//   personToForm(person, as?, today?)  -> a fresh form with this person as the lead actor or as the director
//                                         ("Predict a film with this actor / director", the person page)
//
// Every limit comes from GET /meta/options, like the form's own rules: values the form wouldn't accept (a
// genre outside the 19, a rating outside the list, a runtime out of range) are left out or reset to the default.
import type { MovieDetail, Options } from '@/api/client'
import { DEFAULTS, emptyForm, type FormValues, type NameRef } from '@/form/model'

function spec(options: Options, name: string) {
  return options.fields.find(f => f.name === name)
}

/** TMDB's "NR" is the form's "unrated/unknown"; no rating at all is left for the creator to pick (the model
 *  reads "unrated" as an obscure film, so it shouldn't be chosen silently). */
function certification(rating: string | null | undefined, choices: string[]): string {
  if (rating === 'NR') return choices.find(c => c.startsWith('unrated')) ?? ''
  return rating && choices.includes(rating) ? rating : ''
}

export function filmToForm(film: MovieDetail, options: Options, today = new Date()): FormValues {
  const max = (name: string) => spec(options, name)?.max_items ?? Infinity
  const runtime = spec(options, 'runtime')
  const certifications = spec(options, 'certification')?.choices ?? options.certifications
  const director = film.crew.find(c => c.job === 'Director' && c.name)
  const cast: NameRef[] = [...film.cast]
    .sort((a, b) => (a.order ?? 999) - (b.order ?? 999))
    .filter(c => c.name)
    .slice(0, spec(options, 'actors')?.min_items ?? 5)
    .map(c => ({ id: c.id, name: c.name! }))
  const fits = (n: number | null | undefined) =>
    n != null && (runtime?.min == null || n >= runtime.min) && (runtime?.max == null || n <= runtime.max)

  return {
    ...emptyForm(today),
    genres: film.genres.filter(g => options.genres.includes(g)).slice(0, max('genres')),
    themes: film.themes.filter(t => options.themes.includes(t)).slice(0, max('themes')),
    runtime: fits(film.runtime) ? film.runtime! : DEFAULTS.runtime,
    language: film.original_language && /^[a-z]{2}$/.test(film.original_language) ? film.original_language : DEFAULTS.language,
    certification: certification(film.certification, certifications),
    director: director ? { id: director.id, name: director.name! } : null,
    actors: cast,
  }
}

/** "Predict a film with this actor / director" (the person page): a fresh form with them in that slot. */
export function personToForm(person: { id: number; name: string }, as: 'actor' | 'director' = 'actor',
  today = new Date()): FormValues {
  const ref = { id: person.id, name: person.name }
  return as === 'director' ? { ...emptyForm(today), director: ref } : { ...emptyForm(today), actors: [ref] }
}
