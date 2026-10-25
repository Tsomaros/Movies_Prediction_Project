// Every route of the app, under the shared Layout. Exported as data so tests can mount them in a memory router.
// A page that crashes shows the error page inside the Layout (the header, navigation and footer keep working);
// the outer error page is the last resort, for a crash in the Layout itself.
// Every page but the start page loads on demand, so a visitor downloads only what the page they open needs.
// The form and results pages carry most of the bundle (Zod, Radix, cmdk).
import type { RouteObject } from 'react-router'

import Layout, { type RouteHandle } from '@/app/Layout'
import NotFound, { RouteError } from '@/pages/NotFound'
import Start from '@/pages/Start'

const bleed: RouteHandle = { bleed: true }
const bare: RouteHandle = { bare: true }

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [{
      errorElement: <RouteError />,
      children: [
        { path: '/', element: <Start />, handle: bare },
        { path: '/predict', lazy: () => import('@/pages/Predict').then(m => ({ Component: m.default })) },
        { path: '/predict/result', lazy: () => import('@/pages/PredictResult').then(m => ({ Component: m.default })) },
        { path: '/predict/compare', lazy: () => import('@/pages/PredictCompare').then(m => ({ Component: m.default })) },
        { path: '/movies', lazy: () => import('@/pages/Movies').then(m => ({ Component: m.default })) },
        { path: '/browse', lazy: () => import('@/pages/Browse').then(m => ({ Component: m.default })) },
        { path: '/movies/:id', lazy: () => import('@/pages/MovieDetail').then(m => ({ Component: m.default })) },
        { path: '/people/:id', lazy: () => import('@/pages/Person').then(m => ({ Component: m.default })) },
        { path: '/series', handle: bleed, lazy: () => import('@/pages/Series').then(m => ({ Component: m.default })) },
        { path: '/about', lazy: () => import('@/pages/About').then(m => ({ Component: m.default })) },
        { path: '/login', lazy: () => import('@/pages/Login').then(m => ({ Component: m.default })) },
        { path: '/my-movies', lazy: () => import('@/pages/MyMovies').then(m => ({ Component: m.default })) },
        { path: '*', element: <NotFound /> },
      ],
    }],
  },
]
