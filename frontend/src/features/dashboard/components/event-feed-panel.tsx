import { GlassCard, SectionHeader } from '@/shared/ui'
import { useDashboardAlerts } from '@/features/dashboard/hooks/dashboard-hooks'

const severityStyles: Record<string, string> = {
  high: 'bg-rose-500/10 text-rose-200 border-rose-500/20',
  medium: 'bg-orange-500/10 text-orange-200 border-orange-500/20',
  low: 'bg-slate-600/10 text-slate-200 border-slate-600/20',
}
export default EventFeedPanel
export function EventFeedPanel() {
  const alertsQuery = useDashboardAlerts()
  const alerts = alertsQuery.data ?? []
  const lastUpdated = alertsQuery.dataUpdatedAt ? new Date(alertsQuery.dataUpdatedAt).toLocaleTimeString() : '—'

  return (
    <GlassCard className="p-5">
      <div className="flex items-start justify-between">
        <SectionHeader title="Event Feed" description="Live alerts and trade events" />
        <div className="text-xs text-slate-400">{alertsQuery.isLoading ? 'Loading…' : lastUpdated}</div>
      </div>

      <div className="mt-5 space-y-3">
        {alerts.map((alert: any) => (
          <div key={alert.id} className="rounded-3xl border border-slate-800/70 bg-slate-950/90 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">{alert.label}</p>
                <p className="text-xs text-slate-400">{alert.message}</p>
              </div>
              <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.18em] ${severityStyles[alert.severity]}`}>
                {alert.severity}
              </span>
            </div>
            <p className="mt-3 text-xs text-slate-500">{alert.time ? new Date(alert.time).toLocaleTimeString() : ''}</p>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
