const createId = () => `mock-${Math.random().toString(36).slice(2, 10)}`
const timestamp = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()

export const mockAlerts = [
  {
    id: createId(),
    label: 'Breakout Alert',
    description: 'GAZP pushed above the 55-day range on high volume.',
    severity: 'high' as const,
    time: timestamp(18),
  },
  {
    id: createId(),
    label: 'RSI Warning',
    description: 'ETH RSI entered overbought territory near resistance.',
    severity: 'medium' as const,
    time: timestamp(30),
  },
  {
    id: createId(),
    label: 'AI Risk Signal',
    description: 'Portfolio risk ratio climbed under rising volatility.',
    severity: 'low' as const,
    time: timestamp(42),
  },
  {
    id: createId(),
    label: 'Volume Spike',
    description: 'BTC volume increased 180% on hourly timeframe.',
    severity: 'high' as const,
    time: timestamp(8),
  },
]

export const mockAiMarketBriefing = {
  id: createId(),
  regime: 'Bullish with consolidation risk',
  volatility: 'Moderate - IV Rank at 52%',
  strongest_setups: ['BTC continuation above 68.8k', 'SBER breakout bias', 'IMOEX uptrend intact'],
  narrative: 'Market bias remains bullish but overheated. BTC momentum weakening on lower timeframes. Watch for consolidation into resistance. SBER showing clean breakout continuation setup with volume confirmation.',
  confidence: 0.84,
  sentiment: 'Cautiously bullish',
  time: timestamp(2),
}

export const mockAICopilotHistory = [
  { id: createId(), role: 'assistant' as const, message: 'Ready to help you uncover the next trading edge.' },
  { id: createId(), role: 'user' as const, message: 'Analyze BTC trend' },
  { id: createId(), role: 'assistant' as const, message: 'BTC remains in a bullish regime, but watch the 68.6k resistance band for possible short-term consolidation. EMA alignment is strong, but RSI is showing subtle divergence. Consider scaling into positions carefully.' },
]

export const mockAIPrompts = [
  'Analyze BTC momentum',
  'Find oversold MOEX stocks',
  'Explain portfolio risk',
  'Compare SBER vs IMOEX',
  'What is the market regime?',
  'Show strongest signals',
]

export const mockAnalyticsSummary = {
  signalDistribution: [
    { label: 'Strong Buy', value: 22 },
    { label: 'Buy', value: 30 },
    { label: 'Neutral', value: 28 },
    { label: 'Sell', value: 12 },
    { label: 'Strong Sell', value: 8 },
  ],
  winRate: 74,
  avgConfidence: 0.82,
  volatilityIndex: 37,
}

export const mockSystemStatus = [
  { id: createId(), label: 'API latency', value: '24 ms', status: 'good' as const },
  { id: createId(), label: 'Signal pipeline', value: 'Healthy', status: 'good' as const },
  { id: createId(), label: 'Data feed', value: 'Live', status: 'good' as const },
  { id: createId(), label: 'Auth services', value: 'Operational', status: 'good' as const },
]

export const mockStrategyLibrary = [
  { id: createId(), name: 'Momentum Fusion', description: 'Blend EMA, RSI and volume to find high-conviction entries.', status: 'active' },
  { id: createId(), name: 'Mean Reversion', description: 'Target pullback setups in range-bound securities.', status: 'ready' },
  { id: createId(), name: 'Breakout Pro', description: 'Trade cleanbreakouts above resistance with volume confirmation.', status: 'active' },
]

export const mockJournalEntries = [
  {
    id: createId(),
    title: 'SBER breakout thesis',
    emotion: 'focused',
    notes: 'Position opened on daily breakout with support from RSI and MACD.',
    time: timestamp(260),
  },
  {
    id: createId(),
    title: 'BTC range observation',
    emotion: 'cautious',
    notes: 'Watching the 68.5k level for either consolidation or continuation.',
    time: timestamp(320),
  },
  {
    id: createId(),
    title: 'Portfolio rebalancing',
    emotion: 'disciplined',
    notes: 'Trimmed BTC to secure profits, increased ETH exposure.',
    time: timestamp(400),
  },
]

export const mockUserProfile = {
  username: 'ai.trader',
  email: 'ai.trader@swingtrader.ai',
  role: 'admin',
  joined_at: timestamp(720),
}

export const mockSupportTopics = [
  { id: createId(), title: 'Integrate custom strategy signals', status: 'open' },
  { id: createId(), title: 'Request for new AI explainability views', status: 'in-progress' },
]

export const mockAIReport = {
  report: `
Инструмент AAPL подошёл к зеркальному уровню 190.

Наблюдается локальная консолидация после импульса роста.

RSI на H4 = 72, что указывает на перекупленность.

Объём растёт, но без подтверждения продолжения тренда.

Рекомендация:
— не входить в лонг на текущих уровнях
— ожидать либо ложный пробой уровня 190
— либо откат к зоне 185–186
— при подтверждении слабости покупателя рассматривать шорт
`,
}
