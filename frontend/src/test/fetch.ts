// A fake fetch for tests: answers by path, records every call. Offline, like the Python suite.
// A route can be a function of the URL and the request (its method and body), and may answer later (a Promise),
// so a test can look at the page while a request is still pending.
import { vi } from 'vitest'

type Reply = { status?: number; body?: unknown; headers?: Record<string, string> } | Error

export function mockFetch(routes: Record<string, Reply | ((url: URL, init?: RequestInit) => Reply | Promise<Reply>)>) {
  const calls: { url: URL; init?: RequestInit }[] = []
  const fetch = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, 'http://localhost')
    calls.push({ url, init })
    const route = routes[url.pathname]
    const reply = typeof route === 'function' ? await route(url, init) : route
    if (reply === undefined) return new Response('{"detail":"Not Found"}', { status: 404 })
    if (reply instanceof Error) throw reply
    if (reply.status === 204) return new Response(null, { status: 204 })
    const body = typeof reply.body === 'string' ? reply.body : JSON.stringify(reply.body ?? {})
    return new Response(body, { status: reply.status ?? 200, headers: { 'Content-Type': 'application/json', ...reply.headers } })
  })
  vi.stubGlobal('fetch', fetch)
  return { fetch, calls }
}
