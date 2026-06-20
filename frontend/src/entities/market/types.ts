import { z } from 'zod'

export const marketAssetSchema = z.object({
  id: z.string(),
  symbol: z.string(),
  name: z.string().optional(),
  price: z.number(),
  change_percent: z.number(),
  volume: z.number().optional(),
  signal: z.enum(['BUY', 'SELL', 'NEUTRAL']).optional(),
  ai_score: z.number().min(0).max(100).optional(),
})

export const marketHeatmapItemSchema = z.object({
  symbol: z.string(),
  name: z.string().optional(),
  sector: z.string().optional(),
  regime: z.enum(['Bullish', 'Bearish', 'Neutral']).optional(),
  change_percent: z.number(),
})

export const marketPulseSchema = z.object({
  regime: z.string(),
  volatility: z.string(),
  risk_level: z.string().optional(),
  ai_sentiment: z.number().min(-1).max(1).optional(),
  top_movers: z.array(z.string()).optional(),
})

export const marketCategorySchema = z.enum(['crypto', 'moex', 'nasdaq', 'all'])

export type MarketAsset = z.infer<typeof marketAssetSchema>
export type MarketHeatmapItem = z.infer<typeof marketHeatmapItemSchema>
export type MarketPulse = z.infer<typeof marketPulseSchema>
export type MarketCategory = z.infer<typeof marketCategorySchema>

export const marketAssetArraySchema = z.array(marketAssetSchema)
export const marketHeatmapArraySchema = z.array(marketHeatmapItemSchema)

export default {} as const
