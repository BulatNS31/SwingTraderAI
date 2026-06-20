import { useQuery } from '@tanstack/react-query'
import { mockApi } from '@/shared/api/mock-api'
import { queryKeys } from '@/shared/api/query-keys'

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: queryKeys.analytics.summary,
    queryFn: mockApi.analytics.getSummary,
    staleTime: 30 * 1000,
    retry: 1,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  })
}

export function useAnalyticsSnapshot() {
  return useQuery({
    queryKey: queryKeys.analytics.snapshot,
    queryFn: mockApi.analytics.getSnapshot,
    staleTime: 30 * 1000,
    retry: 1,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  })
}

export function useAnalyticsPulse() {
  return useQuery({
    queryKey: queryKeys.analytics.pulse,
    queryFn: mockApi.analytics.getPulse,
    staleTime: 30 * 1000,
    retry: 1,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  })
}
