import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WakeUpGate from '@/app/WakeUpGate'
import { mockFetch } from '@/test/fetch'

const OK = { body: { status: 'ok' } }
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })
const healthCalls = (calls: { url: URL }[]) => calls.filter((c) => c.url.pathname === '/api/v1/health').length
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
    const { calls } = mockFetch({ '/api/v1/health': () => (up ? OK : new Promise(() => {})) })
    render(<WakeUpGate><p>the app</p></WakeUpGate>)
    await advance(1900)
    expect(overlay()).toBeNull()
    await advance(200)
    expect(overlay()).toHaveTextContent(/waking up the server/i)
    expect(overlay()).toHaveAttribute('role', 'status')
    expect(screen.getByText('the app')).toBeInTheDocument()
    expect(healthCalls(calls)).toBe(1)
    await advance(1000)
    expect(healthCalls(calls)).toBe(2) // t = 3 s
    await advance(3000)
    expect(healthCalls(calls)).toBe(3) // t = 6 s
    up = true
    await advance(3000)
    expect(overlay()).toBeNull()
    await advance(10_000)
    expect(healthCalls(calls)).toBe(4) // stops once healthy
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
