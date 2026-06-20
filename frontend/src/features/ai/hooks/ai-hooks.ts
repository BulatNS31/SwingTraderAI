import { useQuery } from '@tanstack/react-query'
import { mockApi } from '@/shared/api/mock-api'
import { queryKeys } from '@/shared/api/query-keys'

export function useAICopilotHistory() {
  return useQuery({
    queryKey: queryKeys.ai.history,
    queryFn: mockApi.ai.getHistory,
    staleTime: 60 * 1000,
    retry: 1,
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  })
}

export function useAIPrompts() {
  return useQuery({
    queryKey: queryKeys.ai.prompts,
    queryFn: mockApi.ai.getPrompts,
    staleTime: 60 * 1000,
    retry: 1,
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  })
}
