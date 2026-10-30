// The creator form's toolbar: load an example, copy a link to the form, or clear it.
import { EraserIcon, LinkIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { EXAMPLES } from '@/form/examples'
import type { FormValues } from '@/form/model'

export function FormToolbar({ onLoad, onClear, onCopyLink }: {
  onLoad: (values: FormValues) => void
  onClear: () => void
  onCopyLink?: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b pb-4 sm:col-span-2" role="toolbar" aria-label="Form tools">
      <span className="text-muted-foreground text-sm">Try an example:</span>
      {EXAMPLES.map(example => (
        <Button key={example.key} type="button" variant="outline" size="sm" title={example.description}
          onClick={() => onLoad(example.form)}>
          {example.label}
        </Button>
      ))}
      <span className="flex gap-1 sm:ml-auto">
        {onCopyLink && (
          <Button type="button" variant="ghost" size="sm" onClick={onCopyLink}><LinkIcon /> Copy link</Button>
        )}
        <Button type="button" variant="ghost" size="sm" onClick={onClear}>
          <EraserIcon /> Clear form
        </Button>
      </span>
    </div>
  )
}
