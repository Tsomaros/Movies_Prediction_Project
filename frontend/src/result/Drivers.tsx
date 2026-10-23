// "Why": what pushes each estimate up or down, one tab per target (Revenue first). Direction is never colour
// alone: each column has an arrow icon and a heading, and strength is 1–3 bars plus the word.
import { ArrowDownIcon, ArrowUpIcon } from 'lucide-react'

import type { Driver, Prediction } from '@/api/client'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

const TARGETS = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'budget', label: 'Budget' },
  { key: 'score', label: 'Audience score' },
] as const

const STRENGTH = { strong: 3, moderate: 2, slight: 1 } as const

function Strength({ strength, up }: { strength: Driver['strength']; up: boolean }) {
  const n = STRENGTH[strength]
  return (
    <span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
      <span className="inline-flex items-end gap-0.5" aria-hidden>
        {[1, 2, 3].map(i => (
          <span key={i} className={cn('w-1.5 rounded-sm', i === 1 ? 'h-1.5' : i === 2 ? 'h-2.5' : 'h-3.5',
            i <= n ? (up ? 'bg-chart-2' : 'bg-orange-600 dark:bg-orange-400') : 'bg-muted-foreground/25')} />
        ))}
      </span>
      {strength}
    </span>
  )
}

function Column({ drivers, up }: { drivers: Driver[]; up: boolean }) {
  const Icon = up ? ArrowUpIcon : ArrowDownIcon
  return (
    <div className="grid content-start gap-2">
      <h3 className={cn('flex items-center gap-1.5 text-sm font-semibold',
        up ? 'text-[color-mix(in_oklab,var(--chart-2)_75%,black)] dark:text-chart-2' : 'text-orange-700 dark:text-orange-400')}>
        <Icon className="size-4" aria-hidden /> {up ? 'Pushes it up' : 'Pulls it down'}
      </h3>
      {drivers.length === 0 ? (
        <p className="text-muted-foreground text-sm">Nothing notable.</p>
      ) : (
        <ul className="grid gap-2">
          {drivers.map(d => (
            <li key={d.group} className={cn('rounded-md border-l-4 bg-muted/50 px-3 py-2',
              up ? 'border-chart-2' : 'border-orange-600 dark:border-orange-400')}>
              <p className="text-sm">{d.text}</p>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-xs font-medium">{d.label}</span>
                <Strength strength={d.strength} up={up} />
                {d.estimated && <span className="text-muted-foreground text-xs">(the estimated budget)</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function Drivers({ drivers }: { drivers: Prediction['drivers'] }) {
  return (
    <section aria-labelledby="drivers-heading" className="bg-card grid gap-3 rounded-lg border p-4 sm:p-6">
      <div>
        <h2 id="drivers-heading" className="text-lg font-semibold">What drives these estimates</h2>
        <p className="text-muted-foreground text-sm">
          The inputs that moved each estimate most, compared with a typical film. They describe the model's
          reasoning, not proven causes.
        </p>
      </div>
      <Tabs defaultValue="revenue">
        <TabsList className="print:hidden">
          {TARGETS.map(t => <TabsTrigger key={t.key} value={t.key} className="text-foreground/80">{t.label}</TabsTrigger>)}
        </TabsList>
        {TARGETS.map(t => (
          <TabsContent key={t.key} value={t.key} forceMount
            className="focus-visible:outline-ring rounded-md focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-4 data-[state=inactive]:hidden print:data-[state=inactive]:grid">
            <h3 className="mb-2 hidden text-base font-semibold print:block">{t.label}</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <Column drivers={drivers[t.key].up} up />
              <Column drivers={drivers[t.key].down} up={false} />
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </section>
  )
}
