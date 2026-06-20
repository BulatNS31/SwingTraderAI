import { api } from '@/shared/api/axios'
import { parseResponse } from '@/shared/api/schema-utils'
import {
  marketAssetArraySchema,
  marketHeatmapArraySchema,
  marketPulseSchema,
  type MarketAsset,
  type MarketHeatmapItem,
  type MarketPulse,
} from '../types'

export const marketApi = {
  getOverview: async (): Promise<MarketAsset[]> => {
    const resp = await api.get('/markets/overview')
    return parseResponse(marketAssetArraySchema, resp.data)
  },

  getCrypto: async (): Promise<MarketAsset[]> => {
    const resp = await api.get('/markets/crypto')
    return parseResponse(marketAssetArraySchema, resp.data)
  },

  getMoex: async (): Promise<MarketAsset[]> => {
    const resp = await api.get('/markets/moex')
    return parseResponse(marketAssetArraySchema, resp.data)
  },

  getNasdaq: async (): Promise<MarketAsset[]> => {
    const resp = await api.get('/markets/nasdaq')
    return parseResponse(marketAssetArraySchema, resp.data)
  },

  getHeatmap: async (): Promise<MarketHeatmapItem[]> => {
    const resp = await api.get('/markets/heatmap')
    return parseResponse(marketHeatmapArraySchema, resp.data)
  },

  getPulse: async (): Promise<MarketPulse> => {
    const resp = await api.get('/markets/pulse')
    return parseResponse(marketPulseSchema, resp.data)
  },
}

export default marketApi
