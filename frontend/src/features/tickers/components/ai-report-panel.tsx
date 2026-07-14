import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/shared/ui/card'
import { Button } from '@/shared/ui/button'
import { useAIReport, useRegenerateAIReport } from '../hooks/use-ai-report'

interface AIReportPanelProps {
  symbol: string
}

export default function AIReportPanel({
  symbol,
}: AIReportPanelProps) {
  const {
    data,
    isLoading,
    error,
  } = useAIReport(symbol)

  const mutation = useRegenerateAIReport(symbol)

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          Загрузка отчета...
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Resolution</CardTitle>

        <CardDescription>
          Анализ локальной модели
        </CardDescription>
      </CardHeader>

      <CardContent>
        <div className="whitespace-pre-wrap text-sm leading-6">
          {data?.report}
        </div>
      </CardContent>

      <CardFooter>
        <Button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending
            ? 'Генерация...'
            : 'Перегенерировать отчет'}
        </Button>
      </CardFooter>
    </Card>
  )
}
