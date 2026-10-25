// The "Surprise me" state, kept by the header button so the picks survive closing the dialog (the session is the open tab).
//
//   useSurprise()  -> { prefs, setPrefs (saved in the browser), shown (ids picked in this tab), pick (the last answer),
//                      spinning, spin(), startOver(), clearPick() }
//                     clearPick() (on each open) forgets the shown answer but not the ids: the dialog starts at Spin
//                     (its reveal would otherwise replay the old pick), and the next spin still never repeats
//                     spin() asks GET /random with every earlier pick in `exclude`, so Spin again never repeats;
//                     from the watchlist it first needs a login (the login dialog, then the spin)
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'

import { ApiError, api, type RandomPick } from '@/api/client'
import { notifyError } from '@/api/errors'
import { useRequireLogin } from '@/auth/requireLogin'
import { useSessionEnded } from '@/auth/session'
import { loadPrefs, savePrefs, toQuery, type SurprisePrefs } from '@/surprise/prefs'

export function useSurprise() {
  const [prefs, setPrefsState] = useState(loadPrefs)
  const [shown, setShown] = useState<number[]>([])
  const [pick, setPick] = useState<RandomPick | null>(null)
  const requireLogin = useRequireLogin()
  const ended = useSessionEnded()
  const mutation = useMutation({
    mutationFn: (query: ReturnType<typeof toQuery>) => api.random(query),
    onSuccess: answer => {
      setPick(answer)
      if (answer.movie) setShown(ids => [...ids, answer.movie!.id])
    },
    onError: error => {
      if (error instanceof ApiError && error.kind === 'unauthorized') ended()
      if (!notifyError(error)) toast.error(error.message)
    },
  })
  const setPrefs = (patch: Partial<SurprisePrefs>) => {
    const next = { ...prefs, ...patch }
    setPrefsState(next)
    savePrefs(next)
  }
  const spin = () => {
    const run = () => mutation.mutate(toQuery(prefs, shown))
    if (prefs.source === 'watchlist') requireLogin(run)
    else run()
  }
  const startOver = () => {
    setShown([])
    setPick(null)
  }
  return { prefs, setPrefs, shown, pick, spinning: mutation.isPending, spin, startOver, clearPick: () => setPick(null) }
}

export type Surprise = ReturnType<typeof useSurprise>
