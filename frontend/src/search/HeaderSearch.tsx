// The header's search (V1.1). From 768 px the box sits in the header (SearchBox with a dropdown); below that a
// search icon opens a full-screen overlay with the same box and the results under it. The overlay adds a
// history entry while open, so the phone's back gesture closes it; choosing a result replaces that entry.
// "/" anywhere focuses the search (or opens the overlay), except while typing in a field.
import { SearchIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { SearchBox } from '@/search/SearchBox'
import { isTypingTarget } from '@/search/search'

export const DESKTOP = '(min-width: 768px)'

function MobileSearch({ open, onClose }: { open: boolean; onClose: (how: 'back' | 'chosen' | 'dismissed') => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <Dialog open={open} onOpenChange={o => !o && onClose('dismissed')}>
      <DialogContent onOpenAutoFocus={e => { e.preventDefault(); inputRef.current?.focus(); inputRef.current?.select() }}
        className="top-0 left-0 flex h-svh max-h-svh w-full max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-y-auto rounded-none p-4 pt-14 ring-0 sm:max-w-none data-open:zoom-in-100 data-closed:zoom-out-100">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <DialogDescription className="sr-only">Search movies or people; results appear as you type.</DialogDescription>
        <SearchBox variant="overlay" inputRef={inputRef} replace onDone={() => onClose('chosen')} />
      </DialogContent>
    </Dialog>
  )
}

export function HeaderSearch() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [overlay, setOverlay] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(document.activeElement)) return
      e.preventDefault()
      if (window.matchMedia(DESKTOP).matches) inputRef.current?.focus()
      else setOverlay(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => { // the back gesture closes the overlay
    if (!overlay) return
    // once only: React's development mode runs this twice, and a second entry would outlive the overlay
    if (!window.history.state?.searchOverlay) window.history.pushState({ ...window.history.state, searchOverlay: true }, '')
    const onPop = () => setOverlay(false)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [overlay])

  const close = (how: 'back' | 'chosen' | 'dismissed') => {
    setOverlay(false)
    if (how === 'dismissed' && window.history.state?.searchOverlay) window.history.back() // drop our entry
  }

  return (
    <>
      <div className="hidden min-w-0 flex-1 md:block md:max-w-[560px]">
        <SearchBox variant="header" inputRef={inputRef} />
      </div>
      <Button variant="ghost" size="sm" className="ml-auto md:hidden" aria-label="Search" title="Search" onClick={() => setOverlay(true)}>
        <SearchIcon aria-hidden />
      </Button>
      {overlay && <MobileSearch open onClose={close} />}
    </>
  )
}
