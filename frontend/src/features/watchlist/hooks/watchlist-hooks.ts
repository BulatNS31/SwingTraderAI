import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { mockApi } from '@/shared/api/mock-api'
import { apiClient } from '@/shared/api/api-client'
import { queryKeys } from '@/shared/api/query-keys'
import type { CreateWatchlistRequest, WatchlistItem } from '@/shared/api/api-client-types'

export function useWatchlist() {
  return useQuery<WatchlistItem[]>({
    queryKey: queryKeys.watchlist.list,
    queryFn: mockApi.watchlist.getAll,
    staleTime: 10 * 1000,
    retry: 2,
    refetchInterval: 1000, // Watchlist quotes
    refetchIntervalInBackground: false,
  })
}

export function useAddWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateWatchlistRequest) => apiClient.watchlist.add(data),
    onMutate: async (newItem) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.watchlist.list })
      const previous = queryClient.getQueryData<WatchlistItem[]>(queryKeys.watchlist.list)
      if (previous) {
        queryClient.setQueryData<WatchlistItem[]>(queryKeys.watchlist.list, [
          ...previous,
          { id: `temp-${Date.now()}`, ticker_id: newItem.ticker_id, ticker: { id: newItem.ticker_id, symbol: newItem.ticker_id, name: newItem.ticker_id, exchange: 'N/A', price: 0, change: 0, change_percent: 0 }, added_at: new Date().toISOString() },
        ])
      }
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.watchlist.list, context.previous)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist.list })
    },
  })
}

export function useRemoveWatchlistItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => apiClient.watchlist.remove(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.watchlist.list })
      const previous = queryClient.getQueryData<WatchlistItem[]>(queryKeys.watchlist.list)
      if (previous) {
        queryClient.setQueryData<WatchlistItem[]>(queryKeys.watchlist.list, previous.filter((item) => item.id !== id))
      }
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.watchlist.list, context.previous)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist.list })
    },
  })
}
