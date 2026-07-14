import { api } from '@/shared/api/axios'
import { parseResponse } from '@/shared/api/schema-utils'

import {
  candleSchema,
  levelSchema,
  technicalStatusSchema,
  aiReportSchema,
  type Candle,
} from '../schemas/api-schemas'

import {
  mockCandles,
  mockLevels,
  mockTechnicalStatus,
} from '@/shared/mock/candels.mock'

import {
  mockAIReport
} from '@/shared/mock/ai.mock'

import { z } from 'zod'

const candleArraySchema = z.array(candleSchema)
const levelArraySchema = z.array(levelSchema)

// 🔥 переключатель режима
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const tickerApi = {
  async getCandles(
    symbol: string,
    timeframe: 'D1' | 'H4' | 'H1'
  ): Promise<Candle[]> {
    if (USE_MOCK) {
      return mockCandles
    }

    const resp = await api.get(
      `/ticker/${symbol}/candles`,
      {
        params: { tf: timeframe },
      }
    )

    return parseResponse(candleArraySchema, resp.data)
  },

  async getLevels(symbol: string) {
    if (USE_MOCK) {
      return mockLevels
    }

    const resp = await api.get(
      `/ticker/${symbol}/levels`
    )

    return parseResponse(levelArraySchema, resp.data)
  },

  async getTechnicalStatus(symbol: string) {
    if (USE_MOCK) {
      return mockTechnicalStatus
    }

    const resp = await api.get(
      `/ticker/${symbol}/technical`
    )

    return parseResponse(technicalStatusSchema, resp.data)
  },

  async getAIReport(symbol: string) {
    if (USE_MOCK) {
      return mockAIReport
    }

    const resp = await api.get(
      `/ticker/${symbol}/report`
    )

    return parseResponse(aiReportSchema, resp.data)
  },

  async regenerateReport(symbol: string) {
    const resp = await api.post(
      `/ticker/${symbol}/report/regenerate`
    )

    return parseResponse(aiReportSchema, resp.data)
  },
}
