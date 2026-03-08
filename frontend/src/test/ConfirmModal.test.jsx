import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ConfirmModal from '../components/ConfirmModal'

describe('ConfirmModal', () => {
  const defaultProps = {
    open: true,
    title: 'Confirm Action',
    body: 'Are you sure?',
    confirmLabel: 'Delete',
    danger: true,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when open=false', () => {
    render(<ConfirmModal {...defaultProps} open={false} />)
    expect(screen.queryByText('Confirm Action')).toBeNull()
  })

  it('renders title and body when open=true', () => {
    render(<ConfirmModal {...defaultProps} />)
    expect(screen.getByText('Confirm Action')).toBeInTheDocument()
    expect(screen.getByText('Are you sure?')).toBeInTheDocument()
  })

  it('renders custom confirmLabel', () => {
    render(<ConfirmModal {...defaultProps} confirmLabel="Yes, proceed" />)
    expect(screen.getByText('Yes, proceed')).toBeInTheDocument()
  })

  it('calls onConfirm when confirm button clicked', () => {
    render(<ConfirmModal {...defaultProps} />)
    fireEvent.click(screen.getByText('Delete'))
    expect(defaultProps.onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when Cancel button clicked', () => {
    render(<ConfirmModal {...defaultProps} />)
    fireEvent.click(screen.getByText('Cancel'))
    expect(defaultProps.onCancel).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel on Escape key press', () => {
    render(<ConfirmModal {...defaultProps} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(defaultProps.onCancel).toHaveBeenCalledTimes(1)
  })

  it('applies danger (red) style on confirm button when danger=true', () => {
    render(<ConfirmModal {...defaultProps} danger={true} />)
    const btn = screen.getByText('Delete')
    expect(btn.className).toMatch(/red/)
  })

  it('applies non-danger (indigo) style on confirm button when danger=false', () => {
    render(<ConfirmModal {...defaultProps} danger={false} confirmLabel="OK" />)
    const btn = screen.getByText('OK')
    expect(btn.className).toMatch(/indigo/)
  })
})
