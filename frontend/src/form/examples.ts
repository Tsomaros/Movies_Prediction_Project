// The three example films behind the "Try an example" buttons: the golden forms of tests/golden/forms.json
// (the ones the backend's snapshot tests and scripts/smoke.py run), with the names next to the ids so the
// chips can show them. A test checks they still send exactly the golden forms.
import type { FormValues } from '@/form/model'

export type Example = { key: string; label: string; description: string; form: FormValues }

const person = (id: number, name: string) => ({ id, name })
const newName = (name: string) => ({ id: null, name })

export const EXAMPLES: Example[] = [
  {
    key: 'franchise_blockbuster',
    label: 'Superhero sequel',
    description: 'The Russo brothers, the Avengers cast, Marvel, $300M',
    form: {
      genres: ['Action', 'Adventure', 'Science Fiction'], themes: ['superhero', 'science fiction'],
      release_year: 2027, release_month: 5, runtime: 150, language: 'en', certification: 'PG-13',
      director: person(19271, 'Anthony Russo'),
      actors: [person(3223, 'Robert Downey Jr.'), person(16828, 'Chris Evans'), person(1245, 'Scarlett Johansson'),
        person(74568, 'Chris Hemsworth'), person(103, 'Mark Ruffalo')],
      companies: [person(420, 'Marvel Studios')], countries: ['US'], franchise: person(86311, 'The Avengers Collection'),
      synopsis: 'The surviving heroes reunite to stop a cosmic threat that could erase every world they know.',
      budget: 300_000_000,
    },
  },
  {
    key: 'small_drama',
    label: 'Small indie drama',
    description: 'Greta Gerwig, Saoirse Ronan and two newcomers, A24, no budget given',
    form: {
      genres: ['Drama'], themes: ['family', 'coming of age and school'],
      release_year: 2026, release_month: 10, runtime: 105, language: 'en', certification: 'R',
      director: person(45400, 'Greta Gerwig'),
      actors: [person(36592, 'Saoirse Ronan'), person(1373737, 'Florence Pugh'), person(1190668, 'Timothée Chalamet'),
        newName('Ann Newcomer'), newName('Bo Unknown')],
      companies: [person(41077, 'A24')], countries: ['US'], franchise: null,
      synopsis: 'Two sisters return to their small hometown to care for their ailing mother.', budget: null,
    },
  },
  {
    key: 'unknown_cast',
    label: 'Horror, unknown cast',
    description: 'Nobody we know, no studio or country, a $2M budget',
    form: {
      genres: ['Horror', 'Thriller'], themes: ['supernatural'],
      release_year: 2026, release_month: 10, runtime: 92, language: 'en', certification: 'R',
      director: newName('Totally New Director'),
      actors: ['New Actor One', 'New Actor Two', 'New Actor Three', 'New Actor Four', 'New Actor Five'].map(newName),
      companies: [], countries: [], franchise: null, synopsis: '', budget: 2_000_000,
    },
  },
]
