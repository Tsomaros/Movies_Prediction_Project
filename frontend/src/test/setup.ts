// Vitest setup: Testing Library's DOM matchers (toBeInTheDocument, ...), a clean DOM and storage after each test,
// and the browser APIs jsdom lacks (matchMedia, used by next-themes for the system preference).
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

export function mockSystemTheme(dark: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: dark && query.includes('dark'), media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => false,
  }))
}

mockSystemTheme(false)

// Radix (select, popover) and cmdk use browser APIs jsdom doesn't have
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver // not stubGlobal: tests unstub theirs
Element.prototype.scrollIntoView ??= function () {}
window.scrollTo = () => {} // jsdom only logs "not implemented" (React Router's ScrollRestoration calls it)
Element.prototype.hasPointerCapture ??= () => false
Element.prototype.releasePointerCapture ??= () => {}
Element.prototype.setPointerCapture ??= () => {} // sonner's toasts call it on a click

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.className = ''
  mockSystemTheme(false)
})
