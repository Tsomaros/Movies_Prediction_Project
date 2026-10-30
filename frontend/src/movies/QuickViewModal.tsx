// The quick view of a live film that is not in our database (V1.2): poster, title, release date, genres, overview, the
// score or "Not rated yet", and two buttons: "Predict a film like this" (a form started from the film's genres and
// release month) and "View on TMDB" (a new tab). Radix Dialog: focus stays inside, Esc closes, focus goes back.
// Loaded on demand by LiveFilmHost.
import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { LiveMovie } from '@/api/client'
import { useMetaOptions } from '@/api/hooks'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { encodeForm, LIKE_PARAM, URL_PARAM } from '@/form/persist'
import { footerLabel, releaseLine } from '@/lib/live'
import { liveToForm } from '@/movies/predictLike'
import { Poster } from '@/movies/Poster'

export default function QuickViewModal({ film, onClose }: { film: LiveMovie; onClose: () => void }) {
  const navigate = useNavigate()
  const options = useMetaOptions()
  const [opener] = useState(() => document.activeElement) // the card (or the search box) that opened it: focus goes back there
  const predict = () => {
    if (!options.data) return
    navigate(`/predict?${new URLSearchParams({ [URL_PARAM]: encodeForm(liveToForm(film, options.data)), [LIKE_PARAM]: film.title })}`)
  }
  return (
    <Dialog open onOpenChange={open => { if (!open) onClose() }}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-lg"
        onCloseAutoFocus={e => { // there is no Radix trigger (the address opens it), so Radix would leave the focus on the page
          if (opener instanceof HTMLElement && opener.isConnected) { e.preventDefault(); opener.focus() }
        }}>
        <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
          <Poster poster={film.poster} title={film.title} size="large" eager />
          <div className="grid content-start gap-3">
            <DialogTitle className="text-lg leading-tight">{film.title}</DialogTitle>
            <DialogDescription asChild>
              <div className="grid gap-1 text-sm">
                <time dateTime={film.release_date}>{releaseLine(film)}</time>
                {film.genres.length > 0 && <span>{film.genres.join(', ')}</span>}
                <span>{footerLabel(film)}{film.vote_average != null && ` (${film.vote_count.toLocaleString('en-US')} votes)`}</span>
              </div>
            </DialogDescription>
            <p className="text-sm">{film.overview}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={predict} disabled={!options.data}>Predict a film like this</Button>
          <Button asChild variant="outline">
            <a href={`https://www.themoviedb.org/movie/${film.tmdb_id}`} target="_blank" rel="noopener noreferrer">View on TMDB</a>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
