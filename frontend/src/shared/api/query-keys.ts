export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  tickers: {
    all: ['tickers'] as const,
    search: (query: string) => ['tickers', 'search', query] as const,
    detail: (symbol: string) => ['tickers', 'detail', symbol] as const,
    candles: (symbol: string, timeframe: string) => [
      'tickers',
      'detail',
      symbol,
      'candles',
      timeframe,
    ] as const,
    topMovers: ['tickers', 'top-movers'] as const,
  },
  watchlist: {
    list: ['watchlist'] as const,
    item: (id: string) => ['watchlist', id] as const,
  },
  portfolio: {
    positions: ['portfolio', 'positions'] as const,
    summary: ['portfolio', 'summary'] as const,
  },
  indicators: {
    ticker: (symbol: string) => ['indicators', symbol] as const,
  },
  dashboard: {
    overview: ['dashboard', 'overview'] as const,
    signals: ['dashboard', 'signals'] as const,
    heatmap: ['dashboard', 'heatmap'] as const,
    explainability: ['dashboard', 'explainability'] as const,
    alerts: ['dashboard', 'alerts'] as const,
    quickActions: ['dashboard', 'actions'] as const,
  },
  markets: {
    overview: ['markets', 'overview'] as const,
    crypto: ['markets', 'crypto'] as const,
    moex: ['markets', 'moex'] as const,
    nasdaq: ['markets', 'nasdaq'] as const,
    heatmap: ['markets', 'heatmap'] as const,
    pulse: ['markets', 'pulse'] as const,
  },
  analytics: {
    summary: ['analytics', 'summary'] as const,
    snapshot: ['analytics', 'snapshot'] as const,
    pulse: ['analytics', 'pulse'] as const,
  },
  ai: {
    history: ['ai', 'history'] as const,
    prompts: ['ai', 'prompts'] as const,
  },
  scanner: {
    results: ['scanner', 'results'] as const,
  },
  signals: {
    history: ['signals', 'history'] as const,
  },
  aiLab: {
    models: ['ai-lab', 'models'] as const,
    trainingJobs: ['ai-lab', 'training-jobs'] as const,
  },
  alerts: {
    active: ['alerts', 'active'] as const,
  },
  journal: {
    entries: ['journal', 'entries'] as const,
  },
  admin: {
    profile: ['admin', 'profile'] as const,
    support: ['admin', 'support'] as const,
    strategies: ['admin', 'strategies'] as const,
  },
}
