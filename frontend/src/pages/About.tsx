// /about: the project as a short case study: the data, how a prediction is made, how accurate it is (the served
// models' own numbers from GET /model-card), the main limitations, and where the code is.
import { Link } from 'react-router'

import { Accuracy, README_URL } from '@/result/Notes'
import PageHeading from '@/pages/PageHeading'

const REPO_URL = 'https://github.com/Tsomaros/Movies_Prediction_Project'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="grid max-w-prose gap-2 [&_li]:ml-5 [&_li]:list-disc">{children}</div>
    </section>
  )
}

export default function About() {
  return (
    <div className="grid gap-8">
      <PageHeading title="About">
        A tool for film creators to sanity-check a plan: likely budget, box office and audience score, with the reasons
        and similar past films, and honest about how sure it is.
      </PageHeading>

      <Section title="The data">
        <p>
          79,199 films released from 1960 to 2025, pulled from <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer"
            className="text-primary underline">TMDB</a> in October 2026. Money is compared in 2025 US dollars, adjusted with the US
          consumer price index. Only 13% of films report both a budget and a box office, so the money models learn from the
          better-documented films.
        </p>
        <p className="text-muted-foreground text-sm">This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
      </Section>

      <Section title="How a prediction is made">
        <ul>
          <li>Only what is known before release counts: genres, themes, people and their earlier films, studio, franchise, date,
            runtime, rating and budget. Popularity, votes and box office never feed a prediction.</li>
          <li>A film's track record uses only films released before it, and their box office and score only once they are six
            months old, so the models never peek at the future.</li>
          <li>LightGBM models give a low, middle and high value. The ranges are then widened just enough that about 8 in 10 real
            films landed inside them on years the models never saw.</li>
          <li>The reasons come from the models' own arithmetic (SHAP values), grouped into 12 plain-language drivers. They
            describe the model, not proven causes.</li>
        </ul>
      </Section>

      <Accuracy mode="given" />

      <Section title="What it can't do">
        <ul>
          <li>It can't see the script, the marketing or the competition, so breakouts land outside the range.</li>
          <li>Films with budgets over $150M were the weak spot on 2019+ films, and above about $300M a bigger budget no longer
            raises the estimate.</li>
          <li>New films' TMDB scores start high and settle in their first year; the score range is for the settled score.</li>
          <li>Leaving the studio or country empty lowers the ranges, because past films without one are mostly small.</li>
        </ul>
      </Section>

      <Section title="The project">
        <p>
          Built in three weeks as a portfolio project: a data pipeline, time-split evaluation against simple baselines, a FastAPI
          backend and this React app. The code, the test results and every limitation are on{' '}
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="text-primary underline">GitHub</a> (
          <a href={README_URL} target="_blank" rel="noreferrer" className="text-primary underline">README</a>).
        </p>
        <p><Link to="/predict" className="text-primary underline">Plan a film</Link> or <Link to="/browse" className="text-primary underline">browse films</Link>.</p>
      </Section>
    </div>
  )
}
