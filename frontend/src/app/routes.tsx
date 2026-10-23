// Every route of the app, under the shared Layout. Exported as data so tests can mount them in a memory router.
// Every page but the home page loads on demand, so a visitor downloads only what the page they open needs.
// The form and results pages carry most of the bundle (Zod, Radix, cmdk).
import type { RouteObject } from 'react-router'

import Layout from '@/app/Layout'
import Home from '@/pages/Home'
import NotFound, { RouteError } from '@/pages/NotFound'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/predict', lazy: () => import('@/pages/Predict').then(m => ({ Component: m.default })) },
      { path: '/predict/result', lazy: () => import('@/pages/PredictResult').then(m => ({ Component: m.default })) },
      { path: '/movies', lazy: () => import('@/pages/Movies').then(m => ({ Component: m.default })) },
      { path: '/movies/:id', lazy: () => import('@/pages/MovieDetail').then(m => ({ Component: m.default })) },
      { path: '/about', lazy: () => import('@/pages/About').then(m => ({ Component: m.default })) },
      { path: '*', element: <NotFound /> },
    ],
  },
]
