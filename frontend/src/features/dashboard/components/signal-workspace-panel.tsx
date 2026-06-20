import { useMemo } from 'react'
import { GlassCard, SectionHeader, SignalBadge } from '@/shared/ui'
import { useDashboardSignals, useDashboardExplainability } from '@/features/dashboard/hooks/dashboard-hooks'

export function SignalWorkspacePanel() {
  const signalsQuery = useDashboardSignals()
  const explainQuery = useDashboardExplainability()

  const signals = useMemo(() => signalsQuery.data ?? [], [signalsQuery.data])
  const explain = explainQuery.data?.[0]

  const lastUpdated = signalsQuery.dataUpdatedAt ? new Date(signalsQuery.dataUpdatedAt).toLocaleTimeString() : '—'

  return (
    <GlassCard className="p-5">
      <div className="flex items-start justify-between">
        <SectionHeader title="Signal Workspace" description="Top AI signals with explainability" />
        <div className="text-xs text-slate-400">{signalsQuery.isLoading ? 'Loading…' : lastUpdated}</div>
      </div>

      <div className="mt-5 space-y-3">
        {signals.slice(0, 4).map((signal: any) => (
          <div key={signal.id} className="rounded-3xl border border-slate-800/70 bg-slate-950/90 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{signal.ticker}</span>
                  <SignalBadge signal={signal.signal} />
                </div>
                <p className="mt-1 text-xs text-slate-400">{(signal.indicators || []).join(' · ')}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold text-white">{Math.round((signal.confidence ?? 0) * 100)}%</p>
                <p className="text-xs text-slate-500">{signal.time ? new Date(signal.time).toLocaleTimeString() : ''}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {explain && (
        <div className="mt-6 rounded-3xl border border-slate-800/70 bg-slate-950/80 p-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-white">{explain.title}</p>
              <p className="mt-1 text-xs text-slate-400">Why the top signal is active</p>
            </div>
            <span className="rounded-full border border-slate-700 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-400">
              Explainability
            </span>
          </div>

          <ul className="mt-4 grid gap-2 text-sm text-slate-400">
            {explain.reasons.map((reason: string, index: number) => (
              <li key={index} className="flex items-start gap-2">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </GlassCard>
  )
}
export default SignalWorkspacePanel
