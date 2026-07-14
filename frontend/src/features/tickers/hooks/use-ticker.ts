import { useQuery } from '@tanstack/react-query'
import { api } from '@/shared/api/axios'

export interface Level {
  price: number
  type: string
}

async function getTickerLevels(symbol: string) {
  const { data } = await api.get<Level[]>(`/api/ticker/${symbol}/levels`)
  return data
}

export function useTicker(symbol: string) {
  return useQuery({
    queryKey: ['ticker-levels', symbol],
    queryFn: () => getTickerLevels(symbol),
    enabled: !!symbol,
  })
}
