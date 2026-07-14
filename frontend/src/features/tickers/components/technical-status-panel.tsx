import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/shared/ui/card'
import { MetricRow } from '@/shared/ui/metric-row'
import { useTechnicalStatus } from '../hooks/use-technical-status'

interface TechnicalStatusPanelProps {
  symbol: string
}

export default function TechnicalStatusPanel({
  symbol,
}: TechnicalStatusPanelProps) {
  const {
    data,
    isLoading,
    error,
  } = useTechnicalStatus(symbol)

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          Загрузка технического анализа...
        </CardContent>
      </Card>
    )
  }

  if (error instanceof Error) {
    return (
      <Card>
        <CardContent className="p-6 text-red-500">
          {error.message}
        </CardContent>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="p-6">
          Нет данных
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Технический статус</CardTitle>

        <CardDescription>
          Основные показатели инструмента
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-2">
        <MetricRow
          label="ATR"
          value={`${data.atr.toFixed(2)}%`}
        />

        <MetricRow
          label="Запас хода"
          value={`${data.movePercentage.toFixed(2)}%`}
        />

        <MetricRow
          label="До уровня"
          value={`${data.distanceToLevel.toFixed(2)}%`}
        />

        <MetricRow
          label="RSI"
          value={data.rsi.toFixed(2)}
        />

        <MetricRow
          label="Объем"
          value={data.volume.toLocaleString()}
        />

        <MetricRow
          label="Волатильность"
          value={`${data.volatility.toFixed(2)}%`}
        />

        <MetricRow
          label="Сила тренда"
          value={data.trendStrength.toFixed(2)}
        />
      </CardContent>
    </Card>
  )
}
