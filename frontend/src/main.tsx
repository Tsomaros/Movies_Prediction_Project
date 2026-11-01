import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'

import Providers from '@/app/Providers'
import { routes } from '@/app/routes'
import WakeUpGate from '@/app/WakeUpGate'
import { startMonitoring } from '@/lib/monitoring'

import './index.css'

startMonitoring()
const router = createBrowserRouter(routes)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WakeUpGate>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </WakeUpGate>
  </StrictMode>,
)
