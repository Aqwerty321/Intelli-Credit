import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CaseList from '../components/CaseList'

// Mock api.js
vi.mock('../services/api', () => ({
  deleteCase: vi.fn(),
  listCases: vi.fn(),
}))

import { deleteCase, listCases } from '../services/api'

const MOCK_CASES = [
  {
    case_id: 'case_001',
    company_name: 'Sunrise Textiles',
    loan_amount: 5000000,
    loan_purpose: 'Expansion',
    sector: 'textile',
    status: 'complete',
    recommendation: 'APPROVE',
    risk_score: 0.23,
    created_at: '2024-01-15T10:00:00Z',
  },
  {
    case_id: 'case_002',
    company_name: 'Apex Steel',
    loan_amount: 10000000,
    loan_purpose: 'Working Capital',
    sector: 'steel',
    status: 'complete',
    recommendation: 'CONDITIONAL',
    risk_score: 0.55,
    created_at: '2024-01-16T10:00:00Z',
  },
]

describe('CaseList delete column', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listCases.mockResolvedValue(MOCK_CASES)
  })

  it('renders Actions column header', async () => {
    render(<MemoryRouter><CaseList /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Actions')).toBeInTheDocument()
    })
  })

  it('renders Delete button for each case row', async () => {
    render(<MemoryRouter><CaseList /></MemoryRouter>)
    await waitFor(() => {
      const deleteButtons = screen.getAllByText(/🗑 Delete/)
      expect(deleteButtons).toHaveLength(2)
    })
  })

  it('opens confirm modal when Delete button clicked', async () => {
    render(<MemoryRouter><CaseList /></MemoryRouter>)
    await waitFor(() => screen.getAllByText(/🗑 Delete/))
    fireEvent.click(screen.getAllByText(/🗑 Delete/)[0])
    expect(screen.getByText('Delete Case')).toBeInTheDocument()
    // The modal body text contains the company name
    expect(screen.getByText(/Permanently delete/)).toBeInTheDocument()
  })

  it('cancel button closes the modal without deleting', async () => {
    render(<MemoryRouter><CaseList /></MemoryRouter>)
    await waitFor(() => screen.getAllByText(/🗑 Delete/))
    fireEvent.click(screen.getAllByText(/🗑 Delete/)[0])
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Delete Case')).toBeNull()
    expect(deleteCase).not.toHaveBeenCalled()
  })

  it('calls deleteCase with the right case_id on confirm', async () => {
    deleteCase.mockResolvedValue(null)
    listCases
      .mockResolvedValueOnce(MOCK_CASES)
      .mockResolvedValueOnce([])

    render(<MemoryRouter><CaseList /></MemoryRouter>)
    await waitFor(() => screen.getByText('Sunrise Textiles'))
    const sunriseRow = screen.getByText('Sunrise Textiles').closest('tr')
    fireEvent.click(within(sunriseRow).getByText(/🗑 Delete/))
    // Confirm modal's confirm button
    const confirmBtn = screen.getByRole('button', { name: 'Delete' })
    fireEvent.click(confirmBtn)
    await waitFor(() => {
      expect(deleteCase).toHaveBeenCalledWith('case_001')
    })
  })
})
