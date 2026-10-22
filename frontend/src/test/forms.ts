// A complete, valid creator form for tests: picked names (with ids) and new ones (by name).
import { emptyForm, type FormValues } from '@/form/model'

export const VALID: FormValues = {
  ...emptyForm(),
  genres: ['Drama'], themes: ['family'], release_year: 2026, release_month: 10, runtime: 105, language: 'en',
  certification: 'R', director: { id: 45400, name: 'Greta Gerwig', n_films: 4 },
  actors: [{ id: 36592, name: 'Saoirse Ronan' }, { id: null, name: 'Ann Newcomer' }, { id: null, name: 'Bo Unknown' },
    { id: 1373737, name: 'Florence Pugh' }, { id: null, name: ' Cy Fresh ' }],
}
