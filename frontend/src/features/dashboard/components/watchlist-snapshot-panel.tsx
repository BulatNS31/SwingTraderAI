import { GlassCard, SectionHeader } from '@/shared/ui'
import { useWatchlist } from '@/features/watchlist/hooks/watchlist-hooks'

export function WatchlistSnapshotPanel() {
  const q = useWatchlist()
  const items = q.data ?? []
  const lastUpdated = q.dataUpdatedAt ? new Date(q.dataUpdatedAt).toLocaleTimeString() : '—'

  return (
    <GlassCard className="p-5">
      <div className="flex items-start justify-between">
        <SectionHeader title="Watchlist" description="Quick snapshot of tracked tickers" />
        <div className="text-xs text-slate-400">{q.isLoading ? 'Loading…' : lastUpdated}</div>
      </div>

      <div className="mt-5 space-y-3">
        {items.slice(0, 4).map((item: any) => (
          <div key={item.id} className="flex items-center justify-between rounded-3xl border border-slate-800/70 bg-slate-950/90 p-3">
            <div>
              <p className="text-sm font-semibold text-white">{item.ticker?.symbol ?? item.ticker_id ?? item.symbol}</p>
              <p className="text-xs text-slate-500">{item.ticker?.exchange ?? ''}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold text-white">${(item.ticker?.price ?? item.last_price ?? 0).toFixed(2)}</p>
              <p className={`text-xs ${(item.ticker?.change_percent ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(item.ticker?.change_percent ?? 0) >= 0 ? '+' : ''}{(item.ticker?.change_percent ?? 0).toFixed(2)}%
              </p>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
export default WatchlistSnapshotPanel
