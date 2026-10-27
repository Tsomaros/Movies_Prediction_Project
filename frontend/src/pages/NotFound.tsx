// The 404 page, and the error page for a route that crashes (useRouteError) so a bug never shows a blank screen.
import { useEffect } from 'react'
import { isRouteErrorResponse, Link, useRouteError } from 'react-router'

import { Button } from '@/components/ui/button'
import { reportError } from '@/lib/monitoring'
import PageHeading from '@/pages/PageHeading'

export default function NotFound() {
  return (
    <section>
      <PageHeading title="Page not found">There is no page at this address.</PageHeading>
      <Button asChild variant="outline"><Link to="/">Go to the start page</Link></Button>
    </section>
  )
}

export function RouteError() {
  const error = useRouteError()
  const missing = isRouteErrorResponse(error) && error.status === 404
  useEffect(() => {
    if (!missing) reportError(error)
  }, [error, missing])
  if (missing) return <NotFound />
  return (
    <section className="mx-auto max-w-5xl px-4 py-10">
      <PageHeading title="Something went wrong">The page hit an error. Reloading usually helps.</PageHeading>
      <Button onClick={() => window.location.reload()}>Reload</Button>
    </section>
  )
}
