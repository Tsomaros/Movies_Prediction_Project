// A click that needs an account, made while logged out, opens a small login dialog in place; after the login the
// original action completes and the visitor stays on the page (no lost clicks).
//
//   <LoginProvider>        -> wraps the pages (in Layout), holds the dialog and gives useRequireLogin
//                             (src/auth/requireLogin.ts) its answer
import { useCallback, useState, type ReactNode } from 'react'

import { DemoLogin } from '@/auth/DemoLogin'
import { RequireLoginContext, type RequireLogin } from '@/auth/requireLogin'
import { useMe } from '@/auth/session'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export function LoginProvider({ children }: { children: ReactNode }) {
  const { user } = useMe()
  const [pending, setPending] = useState<{ action?: () => void } | null>(null)
  const requireLogin = useCallback<RequireLogin>(action => {
    if (user) action?.()
    else setPending({ action })
  }, [user])
  const done = () => {
    const action = pending?.action
    setPending(null)
    action?.()
  }
  return (
    <RequireLoginContext.Provider value={requireLogin}>
      {children}
      <Dialog open={pending !== null} onOpenChange={open => { if (!open) setPending(null) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Log in to keep track</DialogTitle>
            <DialogDescription>Lists, ratings and notes need an account. The demo account takes one click.</DialogDescription>
          </DialogHeader>
          <DemoLogin onDone={done} />
        </DialogContent>
      </Dialog>
    </RequireLoginContext.Provider>
  )
}
