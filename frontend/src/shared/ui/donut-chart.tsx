"use client"

import React from "react"
import {
  Pie,
  PieChart as ReChartsDonutChart,
  ResponsiveContainer,
  Tooltip,
  Cell,
} from "recharts"

import {
  AvailableChartColors,
  constructCategoryColors,
  getColorClassName,
  type AvailableChartColorsKeys,
} from "@/shared/lib/chartUtils"
import { cx } from "@/shared/lib/cx"

const COLORS: Record<AvailableChartColorsKeys, string> = {
  blue: "#3b82f6",
  cyan: "#06b6d4",
  violet: "#8b5cf6",
  amber: "#f59e0b",
  emerald: "#10b981",
  pink: "#ec4899",
  lime: "#84cc16",
  fuchsia: "#d946ef",
  gray: "#6b7280",
  slate: "#64748b",
  rose: "#f43f5e",
  indigo: "#6366f1",
}

type TooltipProps = Pick<ChartTooltipProps, "active" | "payload">

type PayloadItem = {
  category: string
  value: number
  color: AvailableChartColorsKeys
}

interface ChartTooltipProps {
  active: boolean | undefined
  payload: PayloadItem[]
  valueFormatter: (value: number) => string
}

const ChartTooltip = ({
  active,
  payload,
  valueFormatter,
}: ChartTooltipProps) => {
  if (active && payload && payload.length) {
    return (
      <div
        className={cx(
          "rounded-md border text-sm shadow-md",
          "border-gray-200 dark:border-gray-800",
          "bg-white dark:bg-gray-950",
        )}
      >
        <div className={cx("space-y-1 px-4 py-2")}>
          {payload.map(({ value, category, color }, index) => (
            <div
              key={`id-${index}`}
              className="flex items-center justify-between space-x-8"
            >
              <div className="flex items-center space-x-2">
                <span
                  aria-hidden="true"
                  className={cx(
                    "size-2 shrink-0 rounded-full",
                    getColorClassName(color, "bg"),
                  )}
                />
                <p
                  className={cx(
                    "text-right whitespace-nowrap",
                    "text-gray-700 dark:text-gray-300",
                  )}
                >
                  {category}
                </p>
              </div>
              <p
                className={cx(
                  "text-right font-medium whitespace-nowrap tabular-nums",
                  "text-gray-900 dark:text-gray-50",
                )}
              >
                {valueFormatter(value)}
              </p>
            </div>
          ))}
        </div>
      </div>
    )
  }
  return null
}

type DonutChartVariant = "donut" | "pie"

type BaseEventProps = {
  eventType: "sector"
  categoryClicked: string
  [key: string]: number | string
}

type DonutChartEventProps = BaseEventProps | null | undefined

interface DonutChartProps extends React.HTMLAttributes<HTMLDivElement> {
  data: Record<string, any>[]
  category: string
  value: string
  colors?: AvailableChartColorsKeys[]
  variant?: DonutChartVariant
  valueFormatter?: (value: number) => string
  label?: string
  showLabel?: boolean
  showTooltip?: boolean
  onValueChange?: (value: DonutChartEventProps) => void
  tooltipCallback?: (tooltipCallbackContent: TooltipProps) => void
  customTooltip?: React.ComponentType<TooltipProps>
}

const DonutChart = React.forwardRef<HTMLDivElement, DonutChartProps>(
  (
    {
      data = [],
      value,
      category,
      colors = AvailableChartColors,
      variant = "donut",
      valueFormatter = (value: number) => value.toString(),
      label,
      showLabel = false,
      showTooltip = true,
      onValueChange,
      tooltipCallback,
      customTooltip,
      className,
      ...other
    },
    forwardedRef,
  ) => {
    const isDonut = variant === "donut"
    const [activeIndex, setActiveIndex] = React.useState<number | undefined>(
      undefined,
    )
    const prevActiveRef = React.useRef<boolean | undefined>(undefined)
    const prevCategoryRef = React.useRef<string | undefined>(undefined)
    const CustomTooltip = customTooltip

    // Создаём маппинг цветов для категорий
    const categories = Array.from(new Set(data.map((item) => item[category])))
    const categoryColors = constructCategoryColors(categories, colors)

    // Подготовка данных для отображения
    const preparedData = React.useMemo(() => {
      return data.map((item, index) => ({
        ...item,
        color: categoryColors.get(item[category]) || AvailableChartColors[0],
        fill: COLORS[categoryColors.get(item[category]) || AvailableChartColors[0]],
      }))
    }, [data, categoryColors, category])

    const handleShapeClick = (
      data: any,
      index: number,
      event: React.MouseEvent,
    ) => {
      event.stopPropagation()
      if (!onValueChange) return

      if (activeIndex === index) {
        setActiveIndex(undefined)
        onValueChange(null)
      } else {
        setActiveIndex(index)
        onValueChange({
          eventType: "sector",
          categoryClicked: data.payload[category],
          ...data.payload,
        })
      }
    }

    return (
      <div
        ref={forwardedRef}
        className={className}
        tremor-id="tremor-raw"
        {...other}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ReChartsDonutChart
            onClick={
              onValueChange && activeIndex !== undefined
                ? () => {
                    setActiveIndex(undefined)
                    onValueChange(null)
                  }
                : undefined
            }
            margin={{ top: 0, left: 0, right: 0, bottom: 0 }}
          >
            {showLabel}
            <Pie
              className={cx(
                "stroke-white dark:stroke-gray-950",
                onValueChange ? "cursor-pointer" : "cursor-default",
              )}
              data={preparedData}
              cx="50%"
              cy="50%"
              startAngle={90}
              endAngle={-270}
              innerRadius={isDonut ? "75%" : "0%"}
              outerRadius="100%"
              dataKey={value}
              nameKey={category}
              onClick={handleShapeClick}
              style={{ outline: "none" }}
            >
              {preparedData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.fill}
                  stroke="none"
                />
              ))}
            </Pie>

            {showTooltip && (
              <Tooltip
                wrapperStyle={{ outline: "none" }}
                content={({ active, payload }) => {
                  const cleanPayload = payload
                    ? payload.map((item: any) => ({
                        category: item.payload[category],
                        value: item.value,
                        color: categoryColors.get(
                          item.payload[category],
                        ) as AvailableChartColorsKeys,
                      }))
                    : []

                  const payloadCategory: string = cleanPayload[0]?.category

                  if (
                    tooltipCallback &&
                    (active !== prevActiveRef.current ||
                      payloadCategory !== prevCategoryRef.current)
                  ) {
                    tooltipCallback({
                      active,
                      payload: cleanPayload,
                    })
                    prevActiveRef.current = active
                    prevCategoryRef.current = payloadCategory
                  }

                  return showTooltip && active ? (
                    CustomTooltip ? (
                      <CustomTooltip active={active} payload={cleanPayload} />
                    ) : (
                      <ChartTooltip
                        active={active}
                        payload={cleanPayload}
                        valueFormatter={valueFormatter}
                      />
                    )
                  ) : null
                }}
              />
            )}
          </ReChartsDonutChart>
        </ResponsiveContainer>
      </div>
    )
  },
)

DonutChart.displayName = "DonutChart"

export { DonutChart, type DonutChartEventProps, type TooltipProps }
