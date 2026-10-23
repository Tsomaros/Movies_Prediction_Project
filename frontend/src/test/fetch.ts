// A fake fetch for tests: answers by path, records every call. Offline, like the Python suite.
import { vi } from 'vitest'

type Reply = { status?: number; body?: unknown; headers?: Record<string, string> } | Error

export function mockFetch(routes: Record<string, Reply | ((url: URL, init?: RequestInit) => Reply)>) {
  const calls: { url: URL; init?: RequestInit }[] = []
  const fetch = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, 'http://localhost')
    calls.push({ url, init })
    const route = routes[url.pathname]
    const reply = typeof route === 'function' ? route(url, init) : route
    if (reply === undefined) return new Response('{"detail":"Not Found"}', { status: 404 })
    if (reply instanceof Error) throw reply
    const body = typeof reply.body === 'string' ? reply.body : JSON.stringify(reply.body ?? {})
    return new Response(body, { status: reply.status ?? 200, headers: { 'Content-Type': 'application/json', ...reply.headers } })
  })
  vi.stubGlobal('fetch', fetch)
  return { fetch, calls }
}
