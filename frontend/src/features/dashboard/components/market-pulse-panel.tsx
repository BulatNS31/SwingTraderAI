import { SectionHeader, GlassCard, LivePulseIndicator } from '@/shared/ui'
import { useDashboardOverview } from '@/features/dashboard/hooks/dashboard-hooks'

export default MarketPulsePanel
export function MarketPulsePanel() {
  const q = useDashboardOverview()
  const pulse = q.data ?? {}
  const lastUpdated = q.dataUpdatedAt ? new Date(q.dataUpdatedAt).toLocaleTimeString() : '—'

  return (
    <GlassCard className="p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <SectionHeader
          title="Market Pulse"
          description="Real-time regime, volatility and top mover"
        />

        <div className="text-xs text-slate-400">{q.isLoading ? 'Loading…' : lastUpdated}</div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          <div className="rounded-2xl bg-slate-900/80 p-3">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Regime</p>
            <p className="mt-2 text-sm font-semibold text-white">{pulse.regime ?? '—'}</p>
          </div>
          <div className="rounded-2xl bg-slate-900/80 p-3">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Volatility</p>
            <p className="mt-2 text-sm font-semibold text-white">{pulse.volatility ?? '—'}</p>
          </div>
          <div className="rounded-2xl bg-slate-900/80 p-3">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Top mover</p>
            <p className="mt-2 text-sm font-semibold text-white">{pulse.topMover ?? '—'}</p>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/80 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Live update</p>
          <div className="mt-2 flex items-center gap-2">
            <LivePulseIndicator active size="sm" />
            <p className="text-sm text-slate-300">{q.isFetching ? 'Refreshing' : 'Connected'}</p>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/80 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">AI confidence</p>
          <p className="mt-2 text-sm font-semibold text-white">{Math.round((pulse.confidence ?? 0) * 100)}%</p>
        </div>
        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/80 p-3">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Updated</p>
          <p className="mt-2 text-sm text-slate-300">{lastUpdated}</p>
        </div>
      </div>
    </GlassCard>
  )
}
