import { ArrowUpRight, Sparkles } from 'lucide-react'
import { PageHeader } from '@/shared/ui/page-header'
import { SectionCard } from '@/shared/ui/section-card'
import { SignalBadge } from '@/shared/ui/signal-badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import { useMarketOverview, useCryptoMarket, useMoexMarket, useNasdaqMarket, useMarketHeatmap, useMarketPulse } from '@/features/markets/hooks/market-hooks'
import type { MarketAsset } from '@/entities/market/types'

export function MarketsPage() {
  const overviewQ = useMarketOverview()
  const cryptoQ = useCryptoMarket()
  const moexQ = useMoexMarket()
  const nasdaqQ = useNasdaqMarket()
  const heatmapQ = useMarketHeatmap()
  const pulseQ = useMarketPulse()

  const renderMarketList = (assetsList: MarketAsset[] | undefined, isLoading = false, isError = false) => (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
      {isLoading && <p className="text-sm text-slate-400 py-4">Загрузка...</p>}
      {isError && <p className="text-sm text-rose-400 py-4">Ошибка загрузки данных</p>}
      {!isLoading && !isError && assetsList && assetsList.length === 0 && (
        <p className="text-sm text-slate-500 py-4 text-center">Нет доступных инструментов</p>
      )}
      {!isLoading && !isError && (assetsList ?? []).map((item) => (
        <div
          key={item.id}
          className="rounded-3xl border border-slate-800/90 bg-slate-950/70 p-4 transition hover:-translate-y-0.5 hover:border-slate-700/80"
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-400">{item.symbol}</p>
              <p className="mt-1 text-lg font-semibold text-white">${item.price.toFixed(2)}</p>
              <p className="mt-1 text-xs text-slate-500">Vol {item.volume ?? 0}</p>
            </div>
            <div className="text-right">
              <div className={`text-sm font-semibold ${item.change_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {item.change_percent >= 0 ? '+' : ''}{item.change_percent.toFixed(2)}%
              </div>
              <div className="mt-2 flex items-center justify-end gap-2">
                <SignalBadge signal={item.signal ?? 'NEUTRAL'} />
                <div className="text-xs text-slate-400">AI {item.ai_score?.toFixed(0) ?? '—'}</div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="space-y-8">
      <PageHeader
        title="Рынки"
        description="Ознакомьтесь с ключевыми инструментами, изменениями динамики и общими сигналами рыночной конъюнктуры."
      />

      {/* Основной блок с табами а-ля TradingView */}
      <div className="grid gap-6 lg:grid-cols-[1.8fr_1fr]">
        <SectionCard
          title="Top Market Pulse"
          description="Глобальные компании-лидеры, отобранные с помощью AI и технических решений."
        >
          <Tabs defaultValue="all" className="w-full">
            <TabsList className="mb-4">
              <TabsTrigger value="all">Все рынки</TabsTrigger>
              <TabsTrigger value="crypto">Crypto</TabsTrigger>
              <TabsTrigger value="moex">MOEX</TabsTrigger>
              <TabsTrigger value="nasdaq">NASDAQ</TabsTrigger>
            </TabsList>

            <TabsContent value="all">
              {renderMarketList(overviewQ.data, overviewQ.isLoading, overviewQ.isError)}
            </TabsContent>

            <TabsContent value="crypto">
              {renderMarketList(cryptoQ.data, cryptoQ.isLoading, cryptoQ.isError)}
            </TabsContent>

            <TabsContent value="moex">
              {renderMarketList(moexQ.data, moexQ.isLoading, moexQ.isError)}
            </TabsContent>

            <TabsContent value="nasdaq">
              {renderMarketList(nasdaqQ.data, nasdaqQ.isLoading, nasdaqQ.isError)}
            </TabsContent>
          </Tabs>
        </SectionCard>

        <SectionCard
          title="Live Sector Heat"
          description="Сигналы связаны с импульсом, волатильностью и склонностью к риску."
        >
          <div className="space-y-4">
            {heatmapQ.isLoading && <p className="text-sm text-slate-400 py-4">Загрузка...</p>}
            {heatmapQ.isError && <p className="text-sm text-rose-400 py-4">Ошибка загрузки данных</p>}
            {!heatmapQ.isLoading && !heatmapQ.isError && (heatmapQ.data ?? []).map((item) => (
              <div key={item.symbol} className="flex items-center justify-between rounded-3xl border border-slate-800/90 bg-slate-950/70 p-4">
                <div>
                  <p className="text-sm text-slate-400">{item.symbol}</p>
                  <p className="mt-1 font-semibold text-white">{item.name}</p>
                </div>
                <SignalBadge signal={item.regime === 'Bullish' ? 'BUY' : item.regime === 'Bearish' ? 'SELL' : 'NEUTRAL'} />
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Нижняя часть страницы (Статистика AI и маркетскан) */}
      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Сила режима" description="AI Уровень доверия по основным индексам.">
          <div className="rounded-3xl border border-slate-800/90 bg-slate-950/70 p-6">
            <div className="flex items-center gap-3 text-white">
              <Sparkles className="h-5 w-5 text-amber-400" />
              <div>
                <div className="font-semibold">{pulseQ.data?.regime ?? '—'}</div>
                <div className="text-xs text-slate-400">AI sentiment {pulseQ.data?.ai_sentiment ?? '—'}</div>
              </div>
            </div>
            <p className="mt-4 text-sm text-slate-400">{pulseQ.data ? `Volatility: ${pulseQ.data.volatility}` : 'Загрузка аналитики...'}</p>
          </div>
        </SectionCard>

        <SectionCard title="Market Scan" description="Наиболее перспективные возможности, которые предоставляет система искусственного интеллекта.">
          <div className="grid gap-4">
            <div className="rounded-3xl border border-slate-800/90 bg-slate-950/70 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm text-slate-400">Индикатор импульса</p>
                  <p className="mt-1 text-base font-semibold text-white">BTC выше 50-дневной скользящей средней.</p>
                </div>
                <ArrowUpRight className="h-5 w-5 text-emerald-300" />
              </div>
            </div>
            <div className="rounded-3xl border border-slate-800/90 bg-slate-950/70 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm text-slate-400">Слежение за сопротивлением</p>
                  <p className="mt-1 text-base font-semibold text-white">AAPL находится около отметки 186, импульс снижается.</p>
                </div>
                <ArrowUpRight className="h-5 w-5 text-slate-400" />
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
