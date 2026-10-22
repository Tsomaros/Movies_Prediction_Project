// One labelled form field: the label, an optional hint, the input and its error message, wired for screen
// readers (the input gets `aria-describedby` and `aria-invalid` through the render prop's `a11y`).
import type { ReactNode } from 'react'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

export type A11y = { id: string; 'aria-describedby'?: string; 'aria-invalid'?: true }

export function FormField({ id, label, hint, error, optional, className, children }: {
  id: string
  label: ReactNode
  hint?: ReactNode
  error?: string
  optional?: boolean
  className?: string
  children: (a11y: A11y) => ReactNode
}) {
  const described = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ')
  return (
    <div className={cn('grid content-start gap-2', className)} data-field={id}>
      <Label htmlFor={id} id={`${id}-label`}>
        {label}
        {optional && <span className="text-muted-foreground font-normal">(optional)</span>}
      </Label>
      {children({ id, 'aria-describedby': described || undefined, 'aria-invalid': error ? true : undefined })}
      {hint && <p id={`${id}-hint`} className="text-muted-foreground text-xs">{hint}</p>}
      {error && <p id={`${id}-error`} role="alert" className="text-destructive text-sm">{error}</p>}
    </div>
  )
}
