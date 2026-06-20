export interface MarketPulse {
  regime: string
  volatility: string
  sentiment: string
  confidence: number
}

export interface PortfolioSummary {
  total_value: number
  day_change_percent: number
  total_pnl: number
  win_rate: number
  positions: number
}

export interface SignalItem {
  id: string
  ticker: string
  signal: 'buy' | 'sell' | 'neutral'
  confidence: number
  indicators: string[]
}
