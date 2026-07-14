import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ArrowUpRight, ArrowDownRight } from 'lucide-react'

import { Input } from '@/shared/ui/input'
import { Button } from '@/shared/ui/button'
import { SignalBadge } from '@/shared/ui/signal-badge'
import { GlassCard, SectionHeader, LivePulseIndicator } from '@/shared/ui'

import { useWatchlist } from '@/features/watchlist/hooks/watchlist-hooks'

const assetTypes = ['All', 'Crypto', 'Stocks', 'Russian'] as const

export function WatchlistPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<(typeof assetTypes)[number]>('All')
  const [sortBy, setSortBy] = useState<'signal' | 'change' | 'name'>('signal')

  const watchlistQuery = useWatchlist()
  const items = watchlistQuery.data ?? []

  const openTicker = (symbol: string) => {
    navigate(`/ticker/${symbol}`)
  }

  const getSignal = (symbol: string): 'BUY' | 'SELL' | 'NEUTRAL' => {
    if (symbol === 'TSLA') return 'SELL'
    if (symbol === 'AAPL') return 'BUY'
    return 'NEUTRAL'
  }

  const filtered = useMemo(() => {
    let result = [...items].filter((item) => {
      const searchTerm = search.toLowerCase()
      return (
        item.ticker.symbol.toLowerCase().includes(searchTerm) ||
        item.ticker.name.toLowerCase().includes(searchTerm)
      )
    })

    // Asset type filter
    if (filter !== 'All') {
      result = result.filter((item) => {
        if (filter === 'Crypto') return ['BTC', 'ETH'].includes(item.ticker.symbol)
        if (filter === 'Stocks') return ['AAPL', 'TSLA'].includes(item.ticker.symbol)
        if (filter === 'Russian') return ['SBER', 'GAZP', 'IMOEX'].includes(item.ticker.symbol)
        return true
      })
    }

    // Sorting
    if (sortBy === 'change') {
      result.sort((a, b) => b.ticker.change_percent - a.ticker.change_percent)
    } else if (sortBy === 'name') {
      result.sort((a, b) => a.ticker.symbol.localeCompare(b.ticker.symbol))
    } else if (sortBy === 'signal') {
      const signalOrder = { BUY: 3, NEUTRAL: 2, SELL: 1 }
      result.sort((a, b) => {
        const signalA = getSignal(a.ticker.symbol)
        const signalB = getSignal(b.ticker.symbol)
        return (signalOrder[signalB] || 0) - (signalOrder[signalA] || 0)
      })
    }

    return result
  }, [items, search, filter, sortBy])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Список наблюдения</h1>
        <p className="text-slate-400 mt-1">
          Отслеживайте живые сигналы и AI-анализ на ваших активах
        </p>
      </div>

      {/* Controls */}
      <GlassCard>
        <div className="p-6 space-y-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            {/* Search */}
            <div className="flex-1 flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
              <Search className="h-4 w-4 text-slate-400" />
              <Input
                placeholder="Поиск символов или названий..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="border-0 bg-transparent p-0 text-slate-100 placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 focus:ring-0 !ring-0 !ring-offset-0"
              />
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-2">
              {assetTypes.map((type) => (
                <Button
                  key={type}
                  variant={filter === type ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setFilter(type)}
                  className="rounded-2xl"
                >
                  {type}
                </Button>
              ))}
            </div>
          </div>

          {/* Sort */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 whitespace-nowrap">Сортировать по:</span>
            <div className="flex gap-2">
              {[
                { key: 'signal', label: 'Сила сигнала' },
                { key: 'change', label: 'Изменение цены' },
                { key: 'name', label: 'Название' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setSortBy(key as typeof sortBy)}
                  className={`text-xs px-4 py-1.5 rounded-full transition ${
                    sortBy === key
                      ? 'bg-blue-900/70 text-blue-300'
                      : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Watchlist Items */}
      <div className="space-y-4">
        {filtered.length === 0 ? (
          <GlassCard>
            <div className="p-16 text-center">
              <p className="text-slate-400">Активы не найдены, соответствующие вашим критериям.</p>
            </div>
          </GlassCard>
        ) : (
          filtered.map((item) => {
            const signal = getSignal(item.ticker.symbol)
            const isPositive = item.ticker.change_percent >= 0

            return (
              <GlassCard onClick={() => openTicker(item.ticker.symbol)} key={item.id} className="hover:border-slate-600 transition-all">
                <div className="p-5 sm:p-6">
                  <div className="grid gap-5 sm:grid-cols-[1fr_auto_auto_auto] items-center">
                    {/* Ticker Info */}
                    <div className="flex items-center gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <h3 className="text-xl font-bold">{item.ticker.symbol}</h3>
                          <LivePulseIndicator active={isPositive} size="sm" />
                        </div>
                        <p className="text-sm text-slate-500 mt-0.5">{item.ticker.name}</p>
                      </div>
                    </div>

                    {/* Price */}
                    <div className="sm:text-right">
                      <p className="text-2xl font-semibold text-white">
                        ${item.ticker.price.toFixed(2)}
                      </p>
                      <p
                        className={`text-sm font-medium flex items-center gap-1 sm:justify-end ${
                          isPositive ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {isPositive ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                        {isPositive ? '+' : ''}
                        {item.ticker.change_percent.toFixed(2)}%
                      </p>
                    </div>

                    {/* Signal */}
                    <div className="sm:text-right">
                      <SignalBadge signal={signal} />
                      <p className="text-xs text-slate-500 mt-2">
                        {signal === 'BUY' && '85% confidence'}
                        {signal === 'SELL' && '79% confidence'}
                        {signal === 'NEUTRAL' && '64% confidence'}
                      </p>
                    </div>

                    {/* Action */}
                    <div>
                      <Button className="rounded-2xl px-5">View Setup</Button>
                    </div>
                  </div>

                  {/* AI Insight + Mini Trend */}
                  <div className="mt-6 pt-5 border-t border-slate-800 grid gap-6 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-slate-400 mb-2">24h Trend</p>
                      <div className="flex h-8 gap-0.5 items-end">
                        {Array.from({ length: 24 }).map((_, i) => (
                          <div
                            key={i}
                            className={`flex-1 rounded-t ${isPositive ? 'bg-emerald-500/70' : 'bg-rose-500/70'}`}
                            style={{ height: `${30 + Math.random() * 70}%` }}
                          />
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="text-xs text-slate-400 mb-2">AI Анализ</p>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {item.ticker.symbol === 'AAPL'
                          ? 'Наблюдается позитивный импульс, восстанавливающийся после уровня поддержки. Следите за прорывом выше уровня сопротивления.'
                          : item.ticker.symbol === 'TSLA'
                          ? 'Импульс ослабевает вблизи верхнего предела предложения. Соотношение риска и доходности становится неблагоприятным.'
                          : item.ticker.symbol === 'BTC'
                          ? 'Сильная тенденция к продолжению тренда, но фиксация прибыли вблизи круглых уровней.'
                          : 'Отслеживайте объем последующих действий при попытках прорыва.'}
                      </p>
                    </div>
                  </div>
                </div>
              </GlassCard>
            )
          })
        )}
      </div>

      {/* Stats */}
      <GlassCard>
        <div className="p-6">
          <SectionHeader title="Статистика списка наблюдения" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mt-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-white">{filtered.length}</p>
              <p className="text-xs text-slate-500 mt-1">Отслеживаемые активы</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-emerald-400">
                {filtered.filter((i) => i.ticker.change_percent > 0).length}
              </p>
              <p className="text-xs text-slate-500 mt-1">Прирост</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-rose-400">
                {filtered.filter((i) => i.ticker.change_percent < 0).length}
              </p>
              <p className="text-xs text-slate-500 mt-1">Потери</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-blue-400">3</p>
              <p className="text-xs text-slate-500 mt-1">Сильные сигналы</p>
            </div>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}
