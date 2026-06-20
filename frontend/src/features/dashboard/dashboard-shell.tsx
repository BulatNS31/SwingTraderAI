// React import intentionally omitted — using automatic JSX runtime
import { MarketPulsePanel } from './components/market-pulse-panel'
import { PortfolioHealthPanel } from './components/portfolio-health-panel'
import { SignalWorkspacePanel } from './components/signal-workspace-panel'
import { WatchlistSnapshotPanel } from './components/watchlist-snapshot-panel'
import { EventFeedPanel } from './components/event-feed-panel'
import { TopOpportunitiesPanel } from './components/top-opportunities-panel'
import { ScannerSnapshotPanel } from './components/scanner-snapshot-panel'
import { PortfolioRiskPanel } from './components/portfolio-risk-panel'

export function DashboardShell() {
  return (
    <div className="space-y-4">
      {/* Market pulse full width */}
      <div>
        <MarketPulsePanel />
      </div>

      {/* Main grid: left - signals, right - portfolio/watchlist */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4">
          <SignalWorkspacePanel />
        </div>

        <div className="space-y-4">
          <PortfolioHealthPanel />
          <WatchlistSnapshotPanel />
        </div>
      </div>

      {/* Bottom supporting row */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        <EventFeedPanel />
        <TopOpportunitiesPanel />
        <div className="space-y-4">
          <ScannerSnapshotPanel />
          <PortfolioRiskPanel />
        </div>
      </div>
    </div>
  )
}

export default DashboardShell
