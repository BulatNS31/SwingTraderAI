import { useState } from 'react'
import { PageHeader } from '@/shared/ui/page-header'
import TickerChart from '@/widgets/ticker-chart'
import TechnicalStatusPanel from './technical-status-panel'
import AIReportPanel from './ai-report-panel'
import { useCandles } from '../hooks/use-candles'

interface TickerWorkspaceProps {
  symbol: string
}

export default function TickerWorkspace({
  symbol,
}: TickerWorkspaceProps) {
  const [selectedTimeframe, setSelectedTimeframe] = useState<'D1' | 'H4' | 'H1'>('D1')

  const {
    data: candles,
    isLoading,
  } = useCandles(symbol, selectedTimeframe)

  return (
    <>
      <PageHeader
        title={symbol}
      />

      <div className="flex gap-6 h-full">
        <div className="w-[65%]">
          <TickerChart
              candles={candles ?? []}
              selectedTimeframe={selectedTimeframe}
              onSelectTimeframe={setSelectedTimeframe}
          />
        </div>

        <div className="w-[35%] flex flex-col gap-6">
          <TechnicalStatusPanel symbol={symbol} />

          <AIReportPanel symbol={symbol} />
        </div>
      </div>
    </>
  )
}
