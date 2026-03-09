import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RiskGauge from '../components/charts/RiskGauge'
import RiskWaterfall from '../components/charts/RiskWaterfall'
import CounterfactualBar from '../components/charts/CounterfactualBar'

// Recharts needs ResizeObserver in jsdom
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = globalThis.ResizeObserver || ResizeObserverStub

describe('RiskGauge', () => {
  it('renders risk score percentage', () => {
    render(<RiskGauge riskScore={0.42} size={80} />)
    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('clamps score to [0,1]', () => {
    render(<RiskGauge riskScore={1.5} size={80} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('shows 0% for zero risk', () => {
    render(<RiskGauge riskScore={0} size={80} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })
})

describe('RiskWaterfall', () => {
  it('renders nothing when firings is empty', () => {
    const { container } = render(<RiskWaterfall baseRisk={0.2} firings={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders title when firings are provided', () => {
    const firings = [{ rule_slug: 'dpd_days', risk_adjustment: 0.1, severity: 'HIGH' }]
    render(<RiskWaterfall baseRisk={0.2} firings={firings} />)
    expect(screen.getByText('Risk Score Waterfall')).toBeInTheDocument()
  })
})

describe('CounterfactualBar', () => {
  it('renders nothing when scenarios is empty or missing', () => {
    const { container } = render(<CounterfactualBar scenarios={[]} />)
    expect(container.innerHTML).toBe('')
  })
})
