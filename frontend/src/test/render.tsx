// Render the real routes at a path inside the app's providers, with a fresh query client (no retries).
import { QueryClient } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import Providers from '@/app/Providers'
import { routes } from '@/app/routes'

export function renderApp(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return { router, ...render(<Providers client={client}><RouterProvider router={router} /></Providers>) }
}
