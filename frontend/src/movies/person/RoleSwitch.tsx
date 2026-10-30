// The switch between a person's roles (acting, directing, ...), shown when they have more than one.
import { cn } from '@/lib/utils'

import type { Role, RoleName } from './roles'

export function RoleSwitch({ roles, value, onChange }: { roles: Role[]; value: RoleName; onChange: (r: RoleName) => void }) {
  return (
    <div role="radiogroup" aria-label="Show their work as" className="bg-muted inline-flex max-w-full flex-wrap gap-0.5 rounded-md p-0.5">
      {roles.map(r => (
        <button key={r.role} type="button" role="radio" aria-checked={value === r.role} onClick={() => onChange(r.role)}
          className={cn('inline-flex h-8 items-center gap-1.5 rounded px-2.5 text-sm',
            value === r.role ? 'bg-background font-medium shadow-xs' : 'text-muted-foreground hover:text-foreground')}>
          {r.label} <span className="text-muted-foreground text-xs tabular-nums">{r.films.length}</span>
        </button>
      ))}
    </div>
  )
}
