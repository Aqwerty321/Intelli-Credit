import { useState } from 'react'
import ConfirmModal from '../ConfirmModal'
import {
  relativeTime,
  NOTE_TYPE_BADGE,
  EMPTY_NOTE_FORM,
  sortNotes,
  applyNoteFilters,
} from '../../utils/formatters'

export default function NotesPanel({
  caseId,
  notesList,
  notesLoading,
  noteFilter,
  setNoteFilter,
  noteForm,
  setNoteForm,
  noteEditId,
  setNoteEditId,
  noteSubmitting,
  noteDeleteId,
  setNoteDeleteId,
  onNoteSubmit,
  onNoteEdit,
  onNoteDelete,
  toggleTagFilter,
}) {
  const allNoteTags = [...new Set(notesList.flatMap(n => n.tags || []))]
  const filteredNotes = applyNoteFilters(sortNotes(notesList), noteFilter)

  return (
    <div className="space-y-3">
      <ConfirmModal
        open={!!noteDeleteId}
        title="Delete Note"
        body="This note will be permanently removed."
        confirmLabel="Delete Note"
        onConfirm={onNoteDelete}
        onCancel={() => setNoteDeleteId(null)}
      />

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 items-end bg-slate-50 border border-slate-200 rounded p-2">
        <div>
          <label className="text-[11px] text-slate-500 block mb-0.5">Type</label>
          <select
            value={noteFilter.type}
            onChange={e => setNoteFilter(f => ({ ...f, type: e.target.value }))}
            className="text-xs border border-slate-300 rounded px-2 py-1 bg-white"
          >
            <option value="">All</option>
            <option value="general">General</option>
            <option value="risk">Risk</option>
            <option value="approval">Approval</option>
            <option value="escalation">Escalation</option>
          </select>
        </div>
        <div className="flex-1 min-w-32">
          <label className="text-[11px] text-slate-500 block mb-0.5">Search</label>
          <input
            type="text"
            placeholder="Keyword…"
            value={noteFilter.keyword}
            onChange={e => setNoteFilter(f => ({ ...f, keyword: e.target.value }))}
            className="w-full text-xs border border-slate-300 rounded px-2 py-1"
          />
        </div>
        {allNoteTags.length > 0 && (
          <div>
            <p className="text-[11px] text-slate-500 mb-0.5">Tags (OR)</p>
            <div className="flex flex-wrap gap-1">
              {allNoteTags.map(tag => (
                <button
                  key={tag}
                  onClick={() => toggleTagFilter(tag)}
                  className={`text-[11px] px-1.5 py-0.5 rounded-full border
                    ${noteFilter.tags.includes(tag)
                      ? 'bg-brand text-white border-brand'
                      : 'bg-white text-slate-600 border-slate-300 hover:border-brand'}`}
                >
                  #{tag}
                </button>
              ))}
            </div>
          </div>
        )}
        {(noteFilter.type || noteFilter.keyword || noteFilter.tags.length > 0) && (
          <button
            onClick={() => setNoteFilter({ type: '', keyword: '', tags: [] })}
            className="text-[11px] text-slate-400 hover:text-slate-600"
          >
            Clear
          </button>
        )}
      </div>

      {/* Add / Edit form */}
      <form onSubmit={onNoteSubmit} className="bg-white border border-slate-200 rounded p-3 space-y-2">
        <h3 className="text-xs font-semibold text-slate-700">{noteEditId ? 'Edit Note' : 'Add Note'}</h3>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[11px] text-slate-500 block mb-0.5">Author</label>
            <input
              type="text"
              required
              placeholder="e.g. Priya Singh"
              value={noteForm.author}
              onChange={e => setNoteForm(f => ({ ...f, author: e.target.value }))}
              className="w-full text-xs border border-slate-300 rounded px-2 py-1"
            />
          </div>
          <div>
            <label className="text-[11px] text-slate-500 block mb-0.5">Type</label>
            <select
              value={noteForm.note_type}
              onChange={e => setNoteForm(f => ({ ...f, note_type: e.target.value }))}
              className="w-full text-xs border border-slate-300 rounded px-2 py-1 bg-white"
            >
              <option value="general">General</option>
              <option value="risk">Risk</option>
              <option value="approval">Approval</option>
              <option value="escalation">Escalation</option>
            </select>
          </div>
        </div>
        <div>
          <label className="text-[11px] text-slate-500 block mb-0.5">Note</label>
          <textarea
            required
            rows={2}
            placeholder="Enter note text…"
            value={noteForm.text}
            onChange={e => setNoteForm(f => ({ ...f, text: e.target.value }))}
            className="w-full text-xs border border-slate-300 rounded px-2 py-1 resize-none"
          />
        </div>
        <div className="grid grid-cols-2 gap-2 items-end">
          <div>
            <label className="text-[11px] text-slate-500 block mb-0.5">Tags <span className="text-slate-400">(comma-sep, max 5)</span></label>
            <input
              type="text"
              placeholder="e.g. verified, gst"
              value={noteForm.tags_raw}
              onChange={e => setNoteForm(f => ({ ...f, tags_raw: e.target.value }))}
              className="w-full text-xs border border-slate-300 rounded px-2 py-1"
            />
          </div>
          <label className="flex items-center gap-1.5 text-xs cursor-pointer pb-0.5">
            <input
              type="checkbox"
              checked={noteForm.pinned}
              onChange={e => setNoteForm(f => ({ ...f, pinned: e.target.checked }))}
              className="rounded"
            />
            <span className="text-slate-700">📌 Pin</span>
          </label>
        </div>
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={noteSubmitting}
            className="px-3 py-1 bg-brand text-white text-xs rounded font-medium hover:bg-brand-dark disabled:opacity-40"
          >
            {noteSubmitting ? 'Saving…' : noteEditId ? 'Save' : 'Add'}
          </button>
          {noteEditId && (
            <button
              type="button"
              onClick={() => { setNoteEditId(null); setNoteForm(EMPTY_NOTE_FORM) }}
              className="px-3 py-1 text-xs rounded border border-slate-300 text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
          )}
        </div>
      </form>

      {/* Notes list */}
      {notesLoading ? (
        <p className="text-slate-400 text-xs text-center py-3">Loading notes…</p>
      ) : filteredNotes.length === 0 ? (
        <p className="text-slate-400 text-xs text-center py-3">
          {notesList.length === 0 ? 'No notes yet.' : 'No notes match filters.'}
        </p>
      ) : (
        <div className="space-y-1.5">
          {filteredNotes.map(note => {
            const isEdited = note.updated_at && note.updated_at !== note.created_at
            return (
              <div
                key={note.note_id}
                className={`bg-white rounded border border-slate-200 px-3 py-2 ${note.pinned ? 'border-l-2 border-l-amber-400' : ''}`}
              >
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  {note.pinned && <span className="text-amber-500 text-[11px]">📌</span>}
                  <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded capitalize ${NOTE_TYPE_BADGE[note.note_type] || NOTE_TYPE_BADGE.general}`}>
                    {note.note_type}
                  </span>
                  <span className="text-[11px] font-medium text-slate-700">{note.author}</span>
                  <span className="text-[11px] text-slate-400">{relativeTime(note.created_at)}</span>
                  {isEdited && <span className="text-[11px] text-slate-400">(edited)</span>}
                  <div className="ml-auto flex gap-1.5">
                    <button onClick={() => onNoteEdit(note)} className="text-[11px] text-brand hover:underline">Edit</button>
                    <button onClick={() => setNoteDeleteId(note.note_id)} className="text-[11px] text-red-400 hover:underline">Del</button>
                  </div>
                </div>
                <p className="text-xs text-slate-800 whitespace-pre-wrap">{note.text}</p>
                {note.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {note.tags.map(tag => (
                      <span key={tag} className="text-[11px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">#{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
