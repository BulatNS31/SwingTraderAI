import { GlassCard, SectionHeader } from '@/shared/ui'
import { mockMarketSnapshot } from '@/shared/mock/mock-data'

export function TopOpportunitiesPanel() {
  return (
    <GlassCard className="p-5">
      <SectionHeader title="Top Opportunities" description="High-conviction setups from market scans" />

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {mockMarketSnapshot.map((item) => (
          <div key={item.id} className="rounded-3xl border border-slate-800/70 bg-slate-950/90 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-white">{item.symbol}</p>
              <p className={`text-sm font-semibold ${item.change_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {item.change_percent >= 0 ? '+' : ''}{item.change_percent.toFixed(2)}%
              </p>
            </div>
            <p className="mt-2 text-xs text-slate-400">Candidate for follow-up scan</p>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
export default TopOpportunitiesPanel
