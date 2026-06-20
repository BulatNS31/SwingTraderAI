import { GlassCard, SectionHeader, MetricRow } from '@/shared/ui'
import { usePortfolioSummary } from '@/features/portfolio/hooks/portfolio-hooks'

export function PortfolioHealthPanel() {
  const q = usePortfolioSummary()
  const s = q.data
  const lastUpdated = q.dataUpdatedAt ? new Date(q.dataUpdatedAt).toLocaleTimeString() : '—'

  return (
    <GlassCard className="p-5">
      <div className="flex items-start justify-between">
        <SectionHeader title="Portfolio Health" description="Live equity, P&L, and exposure summary" />
        <div className="text-xs text-slate-400">{q.isLoading ? 'Loading…' : lastUpdated}</div>
      </div>

      <div className="mt-5 space-y-4">
        <MetricRow
          label="Equity"
          value={`$${(s?.total_value ?? 0).toLocaleString()}`}
          trend={s?.day_change_percent > 0 ? 'up' : 'down'}
        />
        <MetricRow
          label="Daily P&L"
          value={`${(s?.day_change_percent ?? 0) > 0 ? '+' : ''}${(s?.day_change_percent ?? 0)}`}
          trend={(s?.day_change_percent ?? 0) > 0 ? 'up' : 'down'}
        />
        <MetricRow
          label="Total P&L"
          value={`$${(s?.total_pnl ?? 0).toLocaleString()}`}
          trend="up"
          secondary={`Win rate ${(s?.win_rate ?? 0)}%`}
        />
      </div>

      <div className="mt-5 rounded-3xl border border-slate-800/70 bg-slate-950/80 p-4">
        <div className="flex items-center justify-between text-xs uppercase tracking-[0.18em] text-slate-500">
          <span>Position exposure</span>
          <span>{s?.positions ?? 0} positions</span>
        </div>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-800">
          <div className="h-full rounded-full bg-emerald-400" style={{ width: `${s?.exposure_percent ?? 0}%` }} />
        </div>
      </div>
    </GlassCard>
  )
}
export default PortfolioHealthPanel
