// /login: the big "Try the demo account" button, with a small password link below. Afterwards the visitor goes
// back to where they came from (?next=, a path on this site only; else /my-movies).
import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { DemoLogin } from '@/auth/DemoLogin'
import { useMe } from '@/auth/session'

function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/login') ? next : '/my-movies'
}

export default function Login() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useMe()
  const next = safeNext(params.get('next'))
  useEffect(() => { if (user) navigate(next, { replace: true }) }, [user, next, navigate])

  return (
    <div className="mx-auto grid w-full max-w-sm gap-6 py-6">
      <title>Log in · Movie Prediction</title>
      <div className="grid gap-1 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Log in</h1>
        <p className="text-muted-foreground text-sm">Keep a watched list with ratings, a watchlist and private notes.</p>
      </div>
      <div className="bg-card rounded-lg border p-5">
        <DemoLogin onDone={() => navigate(next, { replace: true })} />
      </div>
    </div>
  )
}
