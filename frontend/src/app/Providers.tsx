// App-wide providers: the theme, TanStack Query (one client; the API layer sets per-query cache times) and toasts.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { ThemeProvider } from '@/app/theme'
import { Toaster } from '@/components/ui/sonner'

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })
}

export default function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? makeQueryClient())
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster richColors position="bottom-center" />
      </QueryClientProvider>
    </ThemeProvider>
  )
}
