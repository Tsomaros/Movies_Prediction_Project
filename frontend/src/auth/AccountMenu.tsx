// The header's account corner: "Log in" when logged out; when logged in, an initials avatar, a "Demo" chip for
// the shared account and a menu with My movies and Log out.
import { FilmIcon, LogOutIcon } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { toast } from 'sonner'

import { notifyError } from '@/api/errors'
import { useLogout, useMe } from '@/auth/session'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { initials, nameHue } from '@/movies/people'

export function AccountMenu() {
  const { user, isPending } = useMe()
  const logout = useLogout()
  const location = useLocation()
  if (isPending) return <span className="inline-block size-8" aria-hidden />
  if (!user) {
    const next = location.pathname === '/login' ? '' : `?next=${encodeURIComponent(location.pathname + location.search)}`
    return <Button asChild variant="outline" size="sm"><Link to={`/login${next}`}>Log in</Link></Button>
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label={`Account menu for ${user.username}`}
          className="flex items-center gap-1.5 rounded-full p-0.5 pr-1 hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring">
          <span aria-hidden className="inline-flex size-8 items-center justify-center rounded-full text-xs font-semibold text-white"
            style={{ backgroundColor: `hsl(${nameHue(user.username)} 45% 38%)` }}>
            {initials(user.username)}
          </span>
          {user.is_demo && <span className="bg-secondary text-secondary-foreground rounded-full px-2 py-0.5 text-xs font-medium">Demo</span>}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-44">
        <DropdownMenuLabel className="font-normal">Logged in as <span className="font-medium">{user.username}</span></DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild><Link to="/my-movies"><FilmIcon /> My movies</Link></DropdownMenuItem>
        <DropdownMenuItem onSelect={() => logout.mutate(undefined, {
          onSuccess: () => toast.success('Logged out'), onError: error => notifyError(error),
        })}>
          <LogOutIcon /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
