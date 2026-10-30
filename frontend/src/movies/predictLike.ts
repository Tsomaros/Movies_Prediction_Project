// "Predict a film like this": a film's page -> a creator form to start from. The one place that decides what
// carries over, so it is easy to change.
//
//   filmToForm(film, options, today?)  -> FormValues: genres, themes, runtime, language, US rating, the director
//                                         and the top-billed cast; the release date and everything else as a
//                                         fresh form has them (it is a new film, not a remake of this one)
//   personToForm(person, as?, today?)  -> a fresh form with this person as the lead actor or as the director
//                                         ("Predict a film with this actor / director", the person page)
//   liveToForm(film, options, today?)  -> a fresh form started from a live new or upcoming film (V1.2 quick view): its
//                                         genres and release month and year; the creator adds the director, cast and themes
//   recipeToForm(recipe, options, today?) -> FormValues: a Career section model film ("Their usual film",
//                                         "Something new") as scored, plus its median budget; "new" people slots
//                                         are left empty for the creator to name
//
// Every limit comes from GET /meta/options, like the form's own rules: values the form wouldn't accept (a
// genre outside the 19, a rating outside the list, a runtime out of range) are left out or reset to the default.
import type { LiveMovie, MovieDetail, Options, Recipe } from '@/api/client'
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

/** "Predict a film like this" from the quick view of a live film: only what the live data holds (genres and the
 *  release month); a year the form wouldn't accept is left at the usual value. */
export function liveToForm(film: Pick<LiveMovie, 'genres' | 'release_date'>, options: Options, today = new Date()): FormValues {
  const year = spec(options, 'release_year')
  const [y, m] = film.release_date.split('-').map(Number)
  const yearFits = (year?.min == null || y >= year.min) && (year?.max == null || y <= year.max)
  return {
    ...emptyForm(today),
    genres: film.genres.filter(g => options.genres.includes(g)).slice(0, spec(options, 'genres')?.max_items ?? Infinity),
    release_month: m >= 1 && m <= 12 ? m : DEFAULTS.release_month,
    ...(yearFits ? { release_year: y } : {}),
  }
}

/** "Predict a film with this actor / director" (the person page): a fresh form with them in that slot. */
export function personToForm(person: { id: number; name: string }, as: 'actor' | 'director' = 'actor',
  today = new Date()): FormValues {
  const ref = { id: person.id, name: person.name }
  return as === 'director' ? { ...emptyForm(today), director: ref } : { ...emptyForm(today), actors: [ref] }
}

/** "Edit in predictor" (the person page's Career section): the recipe the score model was given. Named people
 *  keep their ids; a "new" slot (and a person without a name) is left out, so the form asks for a real name. */
export function recipeToForm(recipe: Recipe, options: Options, today = new Date()): FormValues {
  const field = (name: string) => spec(options, name)
  const max = (name: string) => field(name)?.max_items ?? Infinity
  const within = (name: string, n: number | null | undefined) => {
    const f = field(name)
    return n != null && (f?.min == null || n >= f.min) && (f?.max == null || n <= f.max)
  }
  const named = (slot: Recipe['director']): NameRef | null =>
    slot !== 'new' && slot.name ? { id: slot.id, name: slot.name } : null
  const country = new RegExp(field('countries')?.pattern ?? '^[A-Z]{2}$')
  const fresh = emptyForm(today)

  return {
    ...fresh,
    genres: recipe.labels.genres.filter(g => options.genres.includes(g)).slice(0, max('genres')),
    themes: recipe.themes.filter(t => options.themes.includes(t)).slice(0, max('themes')),
    runtime: within('runtime', recipe.runtime) ? recipe.runtime : DEFAULTS.runtime,
    language: /^[a-z]{2}$/.test(recipe.language) ? recipe.language : DEFAULTS.language,
    certification: certification(recipe.certification, field('certification')?.choices ?? options.certifications),
    release_year: within('release_year', recipe.release_year) ? recipe.release_year : fresh.release_year,
    release_month: within('release_month', recipe.release_month) ? recipe.release_month : fresh.release_month,
    director: named(recipe.director),
    actors: recipe.actors.map(named).filter((a): a is NameRef => a !== null).slice(0, max('actors')),
    countries: recipe.country && country.test(recipe.country) ? [recipe.country] : [],
    budget: within('budget', recipe.budget_2025) ? recipe.budget_2025 : null,
  }
}
