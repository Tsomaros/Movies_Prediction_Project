// Every route of the app, under the shared Layout. Exported as data so tests can mount them in a memory router.
// The form and results pages load on demand: their libraries (Zod, Radix, cmdk) are most of the bundle, and the
// home page doesn't need them.
import type { RouteObject } from 'react-router'

import Layout from '@/app/Layout'
import Home from '@/pages/Home'
import NotFound, { RouteError } from '@/pages/NotFound'
import { MovieDetail, Movies } from '@/pages/placeholders'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/predict', lazy: () => import('@/pages/Predict').then(m => ({ Component: m.default })) },
      { path: '/predict/result', lazy: () => import('@/pages/PredictResult').then(m => ({ Component: m.default })) },
      { path: '/movies', element: <Movies /> },
      { path: '/movies/:id', element: <MovieDetail /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]
