// Your private notes on a film, like a journal: a box with a 2,000-character counter (Ctrl+Enter saves), then
// the notes newest first, each editable in place (Ctrl+Enter saves, Escape cancels) and deletable with Undo.
// Logged out, it offers the login dialog instead.
import { PencilIcon, Trash2Icon } from 'lucide-react'
import { useState, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import type { Note } from '@/api/client'
import { useRequireLogin } from '@/auth/requireLogin'
import { useMe } from '@/auth/session'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { noteDate, UNDO_MS, useAddNote, useDeleteNote, useEditNote, useFilmNotes } from '@/me/hooks'

const MAX_NOTE = 2000

function NoteBox({ value, onChange, onSave, onCancel, label, saving, saveLabel }: {
  value: string; onChange: (v: string) => void; onSave: () => void; onCancel?: () => void
  label: string; saving: boolean; saveLabel: string
}) {
  const empty = value.trim() === ''
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !empty && !saving) {
      e.preventDefault()
      onSave()
    } else if (e.key === 'Escape' && onCancel) {
      e.preventDefault()
      onCancel()
    }
  }
  return (
    <div className="grid gap-2">
      <Textarea aria-label={label} value={value} maxLength={MAX_NOTE} rows={3} onKeyDown={onKeyDown}
        onChange={e => onChange(e.target.value)} placeholder="What did you think? Only this account sees it." />
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={onSave} disabled={empty || saving}>{saving ? 'Saving…' : saveLabel}</Button>
        {onCancel && <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
        <span className="text-muted-foreground text-xs">Ctrl+Enter to save</span>
        <span className="text-muted-foreground ml-auto text-xs tabular-nums" aria-live="polite">
          {value.length.toLocaleString('en-US')} / {MAX_NOTE.toLocaleString('en-US')}
        </span>
      </div>
    </div>
  )
}

function NoteItem({ note, movieId }: { note: Note; movieId: number }) {
  const [draft, setDraft] = useState<string | null>(null)
  const edit = useEditNote()
  const remove = useDeleteNote(movieId)
  const add = useAddNote(movieId)
  const edited = new Date(note.updated_at).getTime() - new Date(note.created_at).getTime() > 1000
  const save = () => edit.mutate({ id: note.id, body: draft!.trim() }, { onSuccess: () => setDraft(null) })
  const del = () => remove.mutate(note, {
    onSuccess: () => toast('Note deleted', { duration: UNDO_MS, action: { label: 'Undo', onClick: () => add.mutate(note.body) } }),
  })
  return (
    <li className="bg-card grid gap-2 rounded-lg border p-3">
      {draft === null ? (
        <>
          <p className="whitespace-pre-wrap break-words text-sm">{note.body}</p>
          <div className="text-muted-foreground flex items-center gap-1 text-xs">
            <span>{noteDate(note.created_at)}{edited && ' · edited'}</span>
            <Button variant="ghost" size="sm" className="ml-auto h-7" onClick={() => setDraft(note.body)} aria-label="Edit note">
              <PencilIcon /> Edit
            </Button>
            <Button variant="ghost" size="sm" className="h-7" onClick={del} aria-label="Delete note">
              <Trash2Icon /> Delete
            </Button>
          </div>
        </>
      ) : (
        <NoteBox label="Edit note" value={draft} onChange={setDraft} onSave={save} onCancel={() => setDraft(null)}
          saving={edit.isPending} saveLabel="Save" />
      )}
    </li>
  )
}

export function FilmNotes({ movieId }: { movieId: number }) {
  const { user } = useMe()
  const requireLogin = useRequireLogin()
  const notes = useFilmNotes(movieId)
  const add = useAddNote(movieId)
  const [text, setText] = useState('')
  const save = () => add.mutate(text.trim(), { onSuccess: () => setText('') })

  return (
    <section aria-labelledby="notes-heading" className="grid gap-3">
      <h2 id="notes-heading" className="text-lg font-semibold">Your notes</h2>
      {user === null ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-dashed p-4 text-sm">
          <p className="text-muted-foreground">Keep private notes on any film, like a film journal.</p>
          <Button variant="outline" size="sm" onClick={() => requireLogin()}>Log in to write notes</Button>
        </div>
      ) : (
        <>
          <NoteBox label="New note" value={text} onChange={setText} onSave={save} saving={add.isPending} saveLabel="Add note" />
          {notes.data && notes.data.items.length > 0 && (
            <ul className="grid gap-2" aria-label="Notes, newest first">
              {notes.data.items.map(n => <NoteItem key={n.id} note={n} movieId={movieId} />)}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
