// Light/dark theme: starts from the system preference and remembers the creator's choice in localStorage
// ("theme", the same key the no-flash script in index.html reads). next-themes puts the `dark` class on <html>;
// the colours are the CSS variables in index.css.
import { MoonIcon, SunIcon } from 'lucide-react'
import { ThemeProvider as NextThemes, useTheme } from 'next-themes'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'

export const THEME_KEY = 'theme'

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="system" enableSystem storageKey={THEME_KEY} disableTransitionOnChange>
      {children}
    </NextThemes>
  )
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === 'dark'
  return (
    <Button variant="ghost" size="icon" onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
      {dark ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}
