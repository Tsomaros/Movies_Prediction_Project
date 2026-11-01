import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WakeUpGate from '@/app/WakeUpGate'
import { mockFetch } from '@/test/fetch'

const OK = { body: { status: 'ok' } }
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
const healthCalls = (calls: { url: URL }[]) => calls.filter((c) => c.url.pathname === '/api/v1/health').length
// a request that never answers, but ends when it is aborted, like a real fetch
const hang = (_url: URL, init?: RequestInit) => new Promise<never>((_, reject) => {
  init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
})
const overlay = () => screen.queryByTestId('wake-up')

describe('WakeUpGate', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

  it('renders the app at once and never shows the overlay when health answers within 2 s', async () => {
    const { calls } = mockFetch({ '/api/v1/health': async () => { await new Promise((r) => setTimeout(r, 500)); return OK } })
    render(<WakeUpGate><p>the app</p></WakeUpGate>)
    expect(screen.getByText('the app')).toBeInTheDocument()
    await advance(5000)
    expect(overlay()).toBeNull()
    expect(healthCalls(calls)).toBe(1)
  })

  it('shows the overlay after 2 s of no answer, retries every 3 s and hides it when health answers', async () => {
    let up = false
    const { calls } = mockFetch({ '/api/v1/health': (url, init) => (up ? OK : hang(url, init)) })
    render(<WakeUpGate><p>the app</p></WakeUpGate>)
    await advance(1900)
    expect(overlay()).toBeNull()
    await advance(200)
    expect(overlay()).toHaveTextContent(/waking up the server/i)
    expect(screen.getByRole('status')).toContainElement(overlay())
    expect(screen.getByText('the app').parentElement).toHaveAttribute('inert')
    expect(screen.getByText('the app')).toBeInTheDocument()
    expect(healthCalls(calls)).toBe(1)
    await advance(1000)
    expect(healthCalls(calls)).toBe(1) // t = 3 s: the first request is still pending, no second one starts
    await advance(7000)
    expect(healthCalls(calls)).toBe(1) // t = 10 s: the stuck attempt is cancelled
    await advance(2000)
    expect(healthCalls(calls)).toBe(2) // t = 12 s: the next tick retries
    up = true // the attempt of t = 12 s hangs until it is cancelled at t = 22 s; the tick at t = 24 s gets the answer
    await advance(12_000)
    expect(overlay()).toBeNull()
    expect(screen.getByText('the app').parentElement).not.toHaveAttribute('inert')
    await advance(10_000)
    expect(healthCalls(calls)).toBe(3) // stops once healthy
  })

  it('clears the overlay when health answers after 4 s, longer than the retry interval', async () => {
    const { calls } = mockFetch({ '/api/v1/health': async () => { await new Promise((r) => setTimeout(r, 4000)); return OK } })
    render(<WakeUpGate><p>the app</p></WakeUpGate>)
    await advance(2100)
    expect(overlay()).not.toBeNull()
    await advance(2000)
    expect(overlay()).toBeNull()
    expect(healthCalls(calls)).toBe(1)
  })

  it('shows the overlay and retries when the request fails or the server answers with an error', async () => {
    let reply: 'down' | 'error' | 'up' = 'down'
    const { calls } = mockFetch({
      '/api/v1/health': () => (reply === 'down' ? new TypeError('Failed to fetch') : reply === 'error' ? { status: 503 } : OK),
    })
    render(<WakeUpGate><p>the app</p></WakeUpGate>)
    await advance(2100)
    expect(overlay()).not.toBeNull()
    reply = 'error'
    await advance(3000)
    expect(overlay()).not.toBeNull()
    expect(healthCalls(calls)).toBe(2)
    reply = 'up'
    await advance(3000)
    expect(overlay()).toBeNull()
  })
})
