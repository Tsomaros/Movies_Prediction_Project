// The frame around every page: header (brand, navigation, theme toggle), the page, and the footer with TMDB's
// attribution (their logo, unaltered and smaller than ours, the required notice and a link).
// Mobile first: on a phone the navigation is a second row under the brand; from `sm` it sits in the header.
import { ClapperboardIcon } from 'lucide-react'
import { Link, NavLink, Outlet, ScrollRestoration } from 'react-router'

import { ThemeToggle } from '@/app/theme'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/predict', label: 'Plan a film' },
  { to: '/movies', label: 'Browse films' },
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

export function Footer() {
  return (
    <footer className="border-t text-muted-foreground mt-12 print:mt-4">
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
  return (
    <div className="flex min-h-svh flex-col">
      <Header />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:py-10">
        <Outlet />
      </main>
      <Footer />
      <ScrollRestoration /> {/* a new page starts at the top; back and forward return to where you were */}
    </div>
  )
}
