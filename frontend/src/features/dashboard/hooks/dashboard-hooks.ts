import { useQuery } from '@tanstack/react-query'
import { mockApi } from '@/shared/api/mock-api'
import { queryKeys } from '@/shared/api/query-keys'

export function useDashboardOverview() {
  return useQuery({
    queryKey: queryKeys.dashboard.overview,
    queryFn: mockApi.dashboard.getOverview,
    staleTime: 2 * 60 * 1000,
    retry: 1,
    refetchInterval: 5000, // Market / overview cadence
    refetchIntervalInBackground: false,
  })
}

export function useDashboardSignals() {
  return useQuery({
    queryKey: queryKeys.dashboard.signals,
    queryFn: mockApi.dashboard.getSignals,
    staleTime: 30 * 1000,
    retry: 1,
    refetchInterval: 1000, // Active signals
    refetchIntervalInBackground: false,
  })
}

export function useDashboardHeatmap() {
  return useQuery({
    queryKey: queryKeys.dashboard.heatmap,
    queryFn: mockApi.dashboard.getHeatmap,
    staleTime: 4 * 60 * 1000,
    retry: 1,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  })
}

export function useDashboardExplainability() {
  return useQuery({
    queryKey: queryKeys.dashboard.explainability,
    queryFn: mockApi.dashboard.getExplainability,
    staleTime: 60 * 1000,
    retry: 1,
    refetchInterval: 60000, // AI insights cadence
    refetchIntervalInBackground: false,
  })
}

export function useDashboardAlerts() {
  return useQuery({
    queryKey: queryKeys.dashboard.alerts,
    queryFn: mockApi.dashboard.getAlerts,
    staleTime: 10 * 1000,
    retry: 1,
    refetchInterval: 1000, // Alerts feed
    refetchIntervalInBackground: false,
  })
}

export function useDashboardActions() {
  return useQuery({
    queryKey: queryKeys.dashboard.quickActions,
    queryFn: mockApi.dashboard.getQuickActions,
    staleTime: 10 * 60 * 1000,
    retry: 1,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  })
}
