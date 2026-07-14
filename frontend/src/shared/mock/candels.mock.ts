import type { Candle } from '@/shared/api/api-client-types'

export const mockCandles: Candle[] = [
  {
    timestamp: Date.now() - 24 * 60 * 60 * 1000,
    open: 185.50,
    high: 186.20,
    low: 185.10,
    close: 186.00,
    volume: 950000,
  },
  {
    timestamp: Date.now() - 23 * 60 * 60 * 1000,
    open: 186.00,
    high: 187.50,
    low: 185.80,
    close: 187.30,
    volume: 1200000,
  },
  // Коррекция вниз
  {
    timestamp: Date.now() - 22 * 60 * 60 * 1000,
    open: 187.30,
    high: 187.60,
    low: 185.20,
    close: 185.50,
    volume: 1500000,
  },
  // Боковик
  {
    timestamp: Date.now() - 21 * 60 * 60 * 1000,
    open: 185.50,
    high: 186.10,
    low: 185.00,
    close: 185.80,
    volume: 800000,
  },
  {
    timestamp: Date.now() - 20 * 60 * 60 * 1000,
    open: 185.80,
    high: 186.30,
    low: 185.40,
    close: 186.10,
    volume: 750000,
  },
  // Восходящий тренд
  {
    timestamp: Date.now() - 19 * 60 * 60 * 1000,
    open: 186.10,
    high: 188.00,
    low: 186.00,
    close: 187.80,
    volume: 1800000,
  },
  {
    timestamp: Date.now() - 18 * 60 * 60 * 1000,
    open: 187.80,
    high: 189.50,
    low: 187.50,
    close: 189.20,
    volume: 2100000,
  },
  {
    timestamp: Date.now() - 17 * 60 * 60 * 1000,
    open: 189.20,
    high: 190.00,
    low: 188.80,
    close: 189.50,
    volume: 1650000,
  },
  // Резкое падение (плохие новости)
  {
    timestamp: Date.now() - 16 * 60 * 60 * 1000,
    open: 189.50,
    high: 189.70,
    low: 185.00,
    close: 185.50,
    volume: 3500000,
  },
  // Восстановление
  {
    timestamp: Date.now() - 15 * 60 * 60 * 1000,
    open: 185.50,
    high: 187.00,
    low: 185.20,
    close: 186.80,
    volume: 2200000,
  },
  {
    timestamp: Date.now() - 14 * 60 * 60 * 1000,
    open: 186.80,
    high: 188.50,
    low: 186.50,
    close: 188.30,
    volume: 1900000,
  },
  // Снова коррекция
  {
    timestamp: Date.now() - 13 * 60 * 60 * 1000,
    open: 188.30,
    high: 188.60,
    low: 186.80,
    close: 187.20,
    volume: 1400000,
  },
  {
    timestamp: Date.now() - 12 * 60 * 60 * 1000,
    open: 187.20,
    high: 187.50,
    low: 186.00,
    close: 186.30,
    volume: 1100000,
  },
  // Боковик с низкой волатильностью
  {
    timestamp: Date.now() - 11 * 60 * 60 * 1000,
    open: 186.30,
    high: 186.80,
    low: 186.10,
    close: 186.50,
    volume: 600000,
  },
  {
    timestamp: Date.now() - 10 * 60 * 60 * 1000,
    open: 186.50,
    high: 187.20,
    low: 186.30,
    close: 187.00,
    volume: 700000,
  },
  {
    timestamp: Date.now() - 9 * 60 * 60 * 1000,
    open: 187.00,
    high: 187.30,
    low: 186.70,
    close: 186.90,
    volume: 650000,
  },
  // Новый восходящий тренд
  {
    timestamp: Date.now() - 8 * 60 * 60 * 1000,
    open: 186.90,
    high: 188.50,
    low: 186.80,
    close: 188.20,
    volume: 1600000,
  },
  {
    timestamp: Date.now() - 7 * 60 * 60 * 1000,
    open: 188.20,
    high: 190.00,
    low: 188.00,
    close: 189.80,
    volume: 2000000,
  },
  {
    timestamp: Date.now() - 6 * 60 * 60 * 1000,
    open: 189.80,
    high: 191.50,
    low: 189.50,
    close: 191.00,
    volume: 2300000,
  },
  {
    timestamp: Date.now() - 5 * 60 * 60 * 1000,
    open: 191.00,
    high: 192.00,
    low: 190.50,
    close: 191.50,
    volume: 1800000,
  },
  // Фиксация прибыли, откат
  {
    timestamp: Date.now() - 4 * 60 * 60 * 1000,
    open: 191.50,
    high: 191.80,
    low: 189.00,
    close: 189.50,
    volume: 2800000,
  },
  {
    timestamp: Date.now() - 3 * 60 * 60 * 1000,
    open: 189.50,
    high: 190.20,
    low: 188.80,
    close: 189.80,
    volume: 1700000,
  },
  {
    timestamp: Date.now() - 2 * 60 * 60 * 1000,
    open: 189.80,
    high: 190.50,
    low: 189.00,
    close: 190.20,
    volume: 1300000,
  },
  // Последний час - небольшой рост
  {
    timestamp: Date.now() - 1 * 60 * 60 * 1000,
    open: 190.20,
    high: 191.00,
    low: 189.80,
    close: 190.80,
    volume: 1100000,
  },
];

export const mockLevels = [
  {
    price: 185,
    type: 'support',
  },
  {
    price: 190,
    type: 'mirror',
  },
  {
    price: 195,
    type: 'resistance',
  },
]

export const mockTechnicalStatus = {
  atr: 2.41,
  movePercentage: 1.82,
  distanceToLevel: 0.15,
  rsi: 72.4,
  volume: 1250000,
  volatility: 3.2,
  trendStrength: 0.78,
}
