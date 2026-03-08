import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock api.js at module level
vi.mock('../services/api', () => ({
  listNotes: vi.fn(),
  addNote: vi.fn(),
  updateNote: vi.fn(),
  deleteNote: vi.fn(),
}))

import { listNotes, addNote, updateNote, deleteNote } from '../services/api'

// We'll test the notes-related logic via a minimal wrapper component
// that mirrors how CaseDetail uses notes state.
import { useState, useEffect } from 'react'

const MOCK_NOTES = [
  {
    note_id: 'n1',
    author: 'analyst1',
    text: 'First note',
    note_type: 'general',
    tags: ['alpha', 'beta'],
    pinned: true,
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-01T10:00:00Z',
  },
  {
    note_id: 'n2',
    author: 'analyst2',
    text: 'Second note',
    note_type: 'risk',
    tags: ['gamma'],
    pinned: false,
    created_at: '2024-01-02T10:00:00Z',
    updated_at: '2024-01-02T10:00:00Z',
  },
]

/** Minimal notes list fixture component for isolated testing. */
function NotesList({ caseId }) {
  const [notes, setNotes] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    listNotes(caseId)
      .then(setNotes)
      .catch(e => setError(e.message))
  }, [caseId])

  async function handleDelete(noteId) {
    await deleteNote(caseId, noteId)
    setNotes(prev => prev.filter(n => n.note_id !== noteId))
  }

  if (error) return <p data-testid="error">{error}</p>

  return (
    <ul>
      {notes.map(n => (
        <li key={n.note_id} data-testid={`note-${n.note_id}`}>
          <span data-testid={`text-${n.note_id}`}>{n.text}</span>
          {n.pinned && <span data-testid={`pinned-${n.note_id}`}>📌</span>}
          <span data-testid={`tags-${n.note_id}`}>{n.tags.join(',')}</span>
          <button
            data-testid={`delete-${n.note_id}`}
            onClick={() => handleDelete(n.note_id)}
          >Delete</button>
        </li>
      ))}
    </ul>
  )
}

describe('Notes list behaviour', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loaded notes', async () => {
    listNotes.mockResolvedValue(MOCK_NOTES)
    render(<NotesList caseId="case_001" />)
    await waitFor(() => {
      expect(screen.getByTestId('note-n1')).toBeInTheDocument()
      expect(screen.getByTestId('note-n2')).toBeInTheDocument()
    })
  })

  it('displays note text correctly', async () => {
    listNotes.mockResolvedValue(MOCK_NOTES)
    render(<NotesList caseId="case_001" />)
    await waitFor(() => {
      expect(screen.getByTestId('text-n1')).toHaveTextContent('First note')
      expect(screen.getByTestId('text-n2')).toHaveTextContent('Second note')
    })
  })

  it('shows pin indicator only for pinned notes', async () => {
    listNotes.mockResolvedValue(MOCK_NOTES)
    render(<NotesList caseId="case_001" />)
    await waitFor(() => {
      expect(screen.getByTestId('pinned-n1')).toBeInTheDocument()
      expect(screen.queryByTestId('pinned-n2')).toBeNull()
    })
  })

  it('displays tags for each note', async () => {
    listNotes.mockResolvedValue(MOCK_NOTES)
    render(<NotesList caseId="case_001" />)
    await waitFor(() => {
      expect(screen.getByTestId('tags-n1')).toHaveTextContent('alpha')
      expect(screen.getByTestId('tags-n2')).toHaveTextContent('gamma')
    })
  })

  it('removes note from DOM after delete', async () => {
    listNotes.mockResolvedValue([...MOCK_NOTES])
    deleteNote.mockResolvedValue(null)
    render(<NotesList caseId="case_001" />)

    await waitFor(() => screen.getByTestId('note-n1'))
    fireEvent.click(screen.getByTestId('delete-n1'))

    await waitFor(() => {
      expect(screen.queryByTestId('note-n1')).toBeNull()
      expect(screen.getByTestId('note-n2')).toBeInTheDocument()
    })
  })

  it('calls deleteNote with correct caseId and noteId', async () => {
    listNotes.mockResolvedValue([...MOCK_NOTES])
    deleteNote.mockResolvedValue(null)
    render(<NotesList caseId="case_abc" />)
    await waitFor(() => screen.getByTestId('delete-n2'))
    fireEvent.click(screen.getByTestId('delete-n2'))
    await waitFor(() => {
      expect(deleteNote).toHaveBeenCalledWith('case_abc', 'n2')
    })
  })

  it('shows error when listNotes fails', async () => {
    listNotes.mockRejectedValue(new Error('API down'))
    render(<NotesList caseId="case_001" />)
    await waitFor(() => {
      expect(screen.getByTestId('error')).toHaveTextContent('API down')
    })
  })
})
