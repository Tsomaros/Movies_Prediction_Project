// "Surprise me" (Day 14.5): the header's dice button. It keeps the state (useSurprise: the choices, the films
// already picked in this tab, the last pick), so closing the dialog loses nothing, and loads the dialog itself
// (SurpriseDialog.tsx, with its menus) on the first click, so every page's bundle stays as it was.
import { DicesIcon } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useSurprise } from '@/surprise/hooks'

const SurpriseDialog = lazy(() => import('@/surprise/SurpriseDialog'))
const TITLE = 'Surprise me'

export function SurpriseButton() {
  const [open, setOpen] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const surprise = useSurprise()
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => { setLoaded(true); setOpen(true) }} aria-label={TITLE} title={TITLE}>
        <DicesIcon aria-hidden />
        <span className="hidden sm:inline">{TITLE}</span>
      </Button>
      {loaded && (
        <Suspense fallback={null}>
          <SurpriseDialog open={open} onOpenChange={setOpen} surprise={surprise} />
        </Suspense>
      )}
    </>
  )
}
