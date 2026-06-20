import { GlassCard, SectionHeader } from '@/shared/ui'
import { mockScannerResults } from '@/shared/mock/mock-data'

export function ScannerSnapshotPanel() {
  return (
    <GlassCard className="p-5">
      <SectionHeader title="Scanner Snapshot" description="Recent scan matches worth reviewing" />

      <div className="mt-5 space-y-3">
        {mockScannerResults.map((item) => (
          <div key={item.id} className="rounded-3xl border border-slate-800/70 bg-slate-950/90 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">{item.symbol}</p>
                <p className="text-xs text-slate-400">{item.signal}</p>
              </div>
              <span className="rounded-full bg-slate-900 px-2 py-1 text-xs text-slate-300">{Math.round(item.confidence * 100)}%</span>
            </div>
            <p className="mt-2 text-xs text-slate-500">{item.note}</p>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
export default ScannerSnapshotPanel
