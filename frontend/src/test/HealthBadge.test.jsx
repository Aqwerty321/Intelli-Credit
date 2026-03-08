import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

// Mock the api module
vi.mock('../services/api', () => ({
  getHealth: vi.fn(),
  listCases: vi.fn(),
}))

import { getHealth } from '../services/api'

describe('HealthBadge in App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows checking state initially (before getHealth resolves)', () => {
    // getHealth never resolves (pending promise)
    getHealth.mockReturnValue(new Promise(() => {}))
    render(<MemoryRouter><App /></MemoryRouter>)
    // Should show the "checking" indicator while loading
    expect(screen.getByText('⬤ …')).toBeInTheDocument()
  })

  it('shows Healthy badge when getHealth resolves', async () => {
    getHealth.mockResolvedValue({ status: 'ok' })
    render(<MemoryRouter><App /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('🟢 Healthy')).toBeInTheDocument()
    })
  })

  it('shows Offline badge when getHealth rejects', async () => {
    getHealth.mockRejectedValue(new Error('Network error'))
    render(<MemoryRouter><App /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('🔴 Offline')).toBeInTheDocument()
    })
  })

  it('shows v3.0 version string', () => {
    getHealth.mockReturnValue(new Promise(() => {}))
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(screen.getByText(/v3\.0/)).toBeInTheDocument()
  })
})
