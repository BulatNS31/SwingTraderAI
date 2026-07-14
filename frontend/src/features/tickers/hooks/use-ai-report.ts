import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { tickerApi } from '../api/ticker-api'

export function useAIReport(symbol: string) {
  return useQuery({
    queryKey: ['ai-report', symbol],
    queryFn: () => tickerApi.getAIReport(symbol),
    enabled: !!symbol,
  })
}

export function useRegenerateAIReport(symbol: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => tickerApi.regenerateReport(symbol),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['ai-report', symbol],
      })
    },
  })
}
