import { useQuery } from '@tanstack/react-query'
import { tickerApi } from '../api/ticker-api'

export type Timeframe = 'D1' | 'H4' | 'H1'

export function useCandles(
  symbol: string,
  timeframe: Timeframe
) {
  return useQuery({
    queryKey: ['ticker', symbol, 'candles', timeframe],

    queryFn: () =>
      tickerApi.getCandles(symbol, timeframe),

    enabled: !!symbol,

    staleTime: 60_000,
  })
}
