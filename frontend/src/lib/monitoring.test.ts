import { beforeEach, describe, expect, it, vi } from 'vitest'

const init = vi.fn()
const captureException = vi.fn()
vi.mock('@/lib/sentry', () => ({ init, captureException }))

async function load() {
  vi.resetModules()  // the module keeps the loaded SDK: start each test fresh
  return import('@/lib/monitoring')
}

describe('monitoring', () => {
  beforeEach(() => {
    init.mockClear()
    captureException.mockClear()
  })

  it('loads nothing and reports nothing without a DSN', async () => {
    const m = await load()
    m.startMonitoring('')
    m.reportError(new Error('boom'))
    await Promise.resolve()
    expect(init).not.toHaveBeenCalled()
    expect(captureException).not.toHaveBeenCalled()
  })

  it('starts Sentry once with the DSN and reports a crash', async () => {
    const m = await load()
    m.startMonitoring('https://public@o0.ingest.sentry.io/0')
    m.startMonitoring('https://public@o0.ingest.sentry.io/0')
    const error = new Error('boom')
    m.reportError(error)
    await vi.waitFor(() => expect(captureException).toHaveBeenCalledWith(error))
    expect(init).toHaveBeenCalledTimes(1)
    expect(init.mock.calls[0][0]).toMatchObject({ dsn: 'https://public@o0.ingest.sentry.io/0' })
  })
})
