import { GlassCard, SectionHeader } from '@/shared/ui'

export function PortfolioRiskPanel() {
  return (
    <GlassCard className="p-5">
      <SectionHeader title="Portfolio Risk" description="Exposure, concentration and downside alerts" />

      <div className="mt-5 space-y-4">
        <div className="rounded-3xl border border-slate-800/70 bg-slate-950/90 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Concentration</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-white">Top 3 positions</p>
            <span className="text-xs text-slate-400">68%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full w-[68%] rounded-full bg-emerald-400" />
          </div>
        </div>

        <div className="rounded-3xl border border-slate-800/70 bg-slate-950/90 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Downside risk</p>
          <p className="mt-2 text-sm text-slate-300">Moderate — support levels holding, watch leverage.</p>
        </div>
      </div>
    </GlassCard>
  )
}

export default PortfolioRiskPanel
