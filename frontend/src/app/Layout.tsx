// The frame around every page: header (brand, navigation, theme toggle), the page, and the footer with TMDB's
// attribution (their logo, unaltered and smaller than ours, the required notice and a link).
// Mobile first: on a phone the navigation is a second row under the brand; from `sm` it sits in the header.
// A route with `handle: { bleed: true }` (the start page, /series) fills the width between header and footer.
import { ClapperboardIcon } from 'lucide-react'
import { Link, NavLink, Outlet, ScrollRestoration, useMatches } from 'react-router'

import { ThemeToggle } from '@/app/theme'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/movies', label: 'Movies' },
  { to: '/browse', label: 'Browse' },
  { to: '/predict', label: 'Predict' },
  { to: '/about', label: 'About' },
] as const

function Nav({ className }: { className?: string }) {
  return (
    <nav aria-label="Main" className={cn('flex gap-1', className)}>
      {NAV.map(({ to, label }) => (
        <NavLink key={to} to={to}
          className={({ isActive }) => cn(
            'rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
            isActive ? 'bg-accent text-foreground' : 'text-muted-foreground')}>
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function Header() {
  return (
    <header className="print:hidden bg-card/95 supports-backdrop-filter:bg-card/80 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-2">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <ClapperboardIcon className="size-5 text-primary" aria-hidden />
          Movie Prediction
        </Link>
        <Nav className="hidden sm:flex" />
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
      <Nav className="mx-auto max-w-5xl px-2 pb-2 sm:hidden" />
    </header>
  )
}

export type RouteHandle = { bleed?: boolean }

export function Footer({ flush = false }: { flush?: boolean }) {
  return (
    <footer className={cn('border-t text-muted-foreground print:mt-4', !flush && 'mt-12')}>
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-6 text-xs sm:flex-row sm:items-center sm:justify-between">
        <p>Ranges are estimates from past films, not guarantees. <Link to="/about" className="underline">About</Link></p>
        <div data-testid="tmdb-attribution" className="flex items-center gap-3">
          <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer" className="shrink-0">
            <img src="/tmdb-logo.svg" alt="TMDB" width={92} height={12} className="h-3 w-auto" />
          </a>
          <p>This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
        </div>
      </div>
    </footer>
  )
}

export default function Layout() {
  const bleed = useMatches().some(m => (m.handle as RouteHandle | undefined)?.bleed)
  return (
    <div className="flex min-h-svh flex-col">
      <Header />
      <main className={cn('w-full flex-1', bleed ? 'flex flex-col' : 'mx-auto max-w-5xl px-4 py-6 sm:py-10')}>
        <Outlet />
      </main>
      <Footer flush={bleed} />
      {/* A new page starts at the top; back and forward return to where you were. Keyed by the address, because a
          full reload gives every page the same "default" key and would restore another page's position. */}
      <ScrollRestoration getKey={location => location.pathname + location.search} />
    </div>
  )
}
