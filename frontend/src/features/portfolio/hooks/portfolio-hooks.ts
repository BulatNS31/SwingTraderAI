import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { mockApi } from '@/shared/api/mock-api'
import { queryKeys } from '@/shared/api/query-keys'
import { apiClient } from '@/shared/api/api-client'
import type { CreatePositionRequest, Position, PortfolioSummary, UpdatePositionRequest } from '@/shared/api/api-client-types'

export function usePortfolioPositions() {
  return useQuery<Position[]>({
    queryKey: queryKeys.portfolio.positions,
    queryFn: mockApi.portfolio.getPositions,
    staleTime: 3 * 60 * 1000,
    retry: 2,
  })
}

export function usePortfolioSummary() {
  return useQuery<PortfolioSummary>({
    queryKey: queryKeys.portfolio.summary,
    queryFn: mockApi.portfolio.getSummary,
    staleTime: 10 * 1000,
    retry: 2,
    refetchInterval: 5000, // Portfolio summary
    refetchIntervalInBackground: false,
  })
}


export function useAddPosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreatePositionRequest) => apiClient.portfolio.addPosition(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.positions })
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.summary })
    },
  })
}

export function useUpdatePosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdatePositionRequest }) => apiClient.portfolio.updatePosition(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.positions })
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.summary })
    },
  })
}

export function useRemovePosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => apiClient.portfolio.removePosition(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.portfolio.positions })
      const previous = queryClient.getQueryData<Position[]>(queryKeys.portfolio.positions)
      if (previous) {
        queryClient.setQueryData<Position[]>(queryKeys.portfolio.positions, previous.filter((position) => position.id !== id))
      }
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.portfolio.positions, context.previous)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.portfolio.summary })
    },
  })
}
