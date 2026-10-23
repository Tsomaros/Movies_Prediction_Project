// The release-month sweep: the same film released in each month of its planned year (POST /predict/sweep).
//
//   MONTH_VALUES              -> 1..12
//   monthSweep(form)          -> the sweep request for a form
//   rankMonths(points, ratio) -> the best month (highest expected revenue) and the months "about as good": those
//                                whose expected revenue is within the revenue threshold (model card) of the best
import type { PredictForm, SweepRequest, SweepResponse } from '@/api/client'

export const MONTH_VALUES = Array.from({ length: 12 }, (_, i) => i + 1)

export const monthSweep = (form: PredictForm): SweepRequest => ({ form, field: 'release_month', values: MONTH_VALUES })

export function rankMonths(points: SweepResponse['points'], ratio: number | null) {
  const best = points.reduce((a, b) => (b.revenue.middle > a.revenue.middle ? b : a))
  const aboutAsGood = new Set(points
    .filter(p => p !== best && ratio !== null && best.revenue.middle / p.revenue.middle < ratio)
    .map(p => p.value))
  return { best: best.value, aboutAsGood }
}
