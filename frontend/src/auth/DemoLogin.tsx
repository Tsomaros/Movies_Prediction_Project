// The login choices, on /login and in the login dialog: a big "Try the demo account" button first, and a small
// "Log in with password" link that opens a username and password form in place. `onDone` runs after a login.
import { UserRoundIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ApiError } from '@/api/client'
import { notifyError } from '@/api/errors'
import { useDemoLogin, useLogin } from '@/auth/session'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function PasswordForm({ onDone }: { onDone: () => void }) {
  const login = useLogin()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    login.mutate({ username, password }, {
      onSuccess: onDone,
      onError: err => {
        if (err instanceof ApiError && (err.kind === 'unauthorized' || err.kind === 'validation')) {
          setError(err.kind === 'unauthorized' ? err.message : 'Fill in both the username and the password.')
        } else if (!notifyError(err)) toast.error(err.message)
      },
    })
  }
  return (
    <form onSubmit={submit} className="grid gap-3" aria-label="Log in with password">
      <div className="grid gap-1">
        <Label htmlFor="login-username">Username</Label>
        <Input id="login-username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required />
      </div>
      <div className="grid gap-1">
        <Label htmlFor="login-password">Password</Label>
        <Input id="login-password" type="password" autoComplete="current-password" value={password}
          onChange={e => setPassword(e.target.value)} required />
      </div>
      {error && <p role="alert" className="text-destructive text-sm">{error}</p>}
      <Button type="submit" variant="outline" disabled={login.isPending}>{login.isPending ? 'Logging in…' : 'Log in'}</Button>
    </form>
  )
}

export function DemoLogin({ onDone }: { onDone: () => void }) {
  const demo = useDemoLogin()
  const [withPassword, setWithPassword] = useState(false)
  return (
    <div className="grid gap-4">
      <div className="grid gap-1.5">
        <Button size="lg" onClick={() => demo.mutate(undefined, { onSuccess: onDone, onError: err => { if (!notifyError(err)) toast.error(err.message) } })}
          disabled={demo.isPending}>
          <UserRoundIcon /> {demo.isPending ? 'Logging in…' : 'Try the demo account'}
        </Button>
        <p className="text-muted-foreground text-center text-xs">
          No sign-up. Everyone shares this account, and its lists and notes reset every night.
        </p>
      </div>
      {withPassword ? <PasswordForm onDone={onDone} /> : (
        <button type="button" onClick={() => setWithPassword(true)}
          className="text-muted-foreground justify-self-center text-sm underline underline-offset-2 hover:text-foreground">
          Log in with password
        </button>
      )}
    </div>
  )
}
