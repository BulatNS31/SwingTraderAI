import { useEffect, useMemo, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useTheme } from 'next-themes'

import { Button } from '@/shared/ui/button'
import type { Candle } from '@/shared/api/api-client-types'
import { mockLevels } from '@/shared/mock/candels.mock'

interface TickerChartProps {
  candles: Candle[]
  selectedTimeframe: 'D1' | 'H4' | 'H1'
  onSelectTimeframe: (timeframe: 'D1' | 'H4' | 'H1') => void
}

const timeframeOptions = ['D1', 'H4', 'H1'] as const

export default function TickerChart({
  candles,
  selectedTimeframe,
  onSelectTimeframe,
}: TickerChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const chartRef = useRef<IChartApi | null>(null)

  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  const seriesData = useMemo<CandlestickData[]>(() => {
    return candles.map((candle) => ({
      time: Math.floor(candle.timestamp / 1000) as UTCTimestamp,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }))
  }, [candles])

  const { resolvedTheme } = useTheme()

  const isDark = resolvedTheme === 'dark'

  const chartColors = {
    background: 'transparent',
    text: isDark ? '#f8fafc' : '#0f172a',
    grid: isDark
      ? 'rgba(148,163,184,.08)'
      : 'rgba(100,116,139,.15)',
    border: isDark
      ? 'rgba(148,163,184,.15)'
      : 'rgba(100,116,139,.25)',
  }

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,

      layout: {
        background: {
          color: 'transparent',
        },
        textColor: 'var(--foreground)',
      },

      grid: {
        vertLines: {
          color: 'rgba(148,163,184,.08)',
        },
        horzLines: {
          color: 'rgba(148,163,184,.08)',
        },
      },

      rightPriceScale: {
        borderColor: 'rgba(148,163,184,.15)',
      },

      timeScale: {
        borderColor: 'rgba(148,163,184,.15)',
        timeVisible: true,
        secondsVisible: false,
      },

      crosshair: {
        mode: 1,
      },

      localization: {
        locale: 'en-US',
      },
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',

      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',

      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries

    const resizeObserver = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) return

      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      })
    })

    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!chartRef.current) return

    chartRef.current.applyOptions({
      layout: {
        textColor: chartColors.text,
      },
      grid: {
        vertLines: {
          color: chartColors.grid,
        },
        horzLines: {
          color: chartColors.grid,
        },
      },
      rightPriceScale: {
        borderColor: chartColors.border,
      },
      timeScale: {
        borderColor: chartColors.border,
      },
    })
  }, [resolvedTheme])

  useEffect(() => {
    if (!candleSeriesRef.current) return

    candleSeriesRef.current.setData(seriesData)

    // очищаем старые уровни (важно)
    candleSeriesRef.current.priceLines().forEach(line => {
      candleSeriesRef.current?.removePriceLine(line)
    })

    mockLevels.forEach(level => {
      candleSeriesRef.current?.createPriceLine({
        price: level.price,
        color:
          level.type === 'support'
            ? '#22c55e'
            : level.type === 'resistance'
              ? '#ef4444'
              : '#f59e0b',
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: level.type,
      })
    })

    chartRef.current?.timeScale().fitContent()
  }, [seriesData])

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">
            Свечной график
          </h2>
        </div>

        <div className="flex gap-2">
          {timeframeOptions.map((tf) => (
            <Button
              key={tf}
              variant={selectedTimeframe === tf ? 'default' : 'outline'}
              size="sm"
              onClick={() => onSelectTimeframe(tf)}
            >
              {tf}
            </Button>
          ))}
        </div>
      </div>

      <div
        ref={containerRef}
        className="h-[650px] w-full"
      />
    </div>
  )
}
