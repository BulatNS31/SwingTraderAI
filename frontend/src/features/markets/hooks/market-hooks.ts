import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/shared/api/query-keys'
import { marketApi } from '@/entities/market/api/market-api'
import type { MarketAsset, MarketHeatmapItem, MarketPulse } from '@/entities/market/types'

export function useMarketOverview() {
  return useQuery<MarketAsset[]>({
    queryKey: queryKeys.markets.overview,
    queryFn: marketApi.getOverview,
    staleTime: 5000,
    retry: 1,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
}

export function useCryptoMarket() {
  return useQuery<MarketAsset[]>({
    queryKey: queryKeys.markets.crypto,
    queryFn: marketApi.getCrypto,
    staleTime: 5000,
    retry: 1,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
}

export function useMoexMarket() {
  return useQuery<MarketAsset[]>({
    queryKey: queryKeys.markets.moex,
    queryFn: marketApi.getMoex,
    staleTime: 5000,
    retry: 1,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
}

export function useNasdaqMarket() {
  return useQuery<MarketAsset[]>({
    queryKey: queryKeys.markets.nasdaq,
    queryFn: marketApi.getNasdaq,
    staleTime: 5000,
    retry: 1,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
}

export function useMarketHeatmap() {
  return useQuery<MarketHeatmapItem[]>({
    queryKey: queryKeys.markets.heatmap,
    queryFn: marketApi.getHeatmap,
    staleTime: 15000,
    retry: 1,
    refetchInterval: 15000,
    refetchIntervalInBackground: false,
  })
}

export function useMarketPulse() {
  return useQuery<MarketPulse>({
    queryKey: queryKeys.markets.pulse,
    queryFn: marketApi.getPulse,
    staleTime: 15000,
    retry: 1,
    refetchInterval: 15000,
    refetchIntervalInBackground: false,
  })
}

export default {} as const
