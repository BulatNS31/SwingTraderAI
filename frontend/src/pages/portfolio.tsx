import { useState } from 'react'
import { ArrowUpRight, ArrowDownRight, TrendingUp, Calendar } from 'lucide-react'

import { DonutChart } from "@/shared/ui/donut-chart"
import {
  GlassCard,
  SectionHeader,
} from '@/shared/ui'

import { usePortfolioSummary, usePortfolioPositions } from '@/features/portfolio/hooks/portfolio-hooks'

const tabs = ['Обзор', 'Доход', 'Результат', 'Новости', 'Инвестиции'] as const
type TabType = typeof tabs[number]

export function PortfolioPage() {
  const [activeTab, setActiveTab] = useState<TabType>('Обзор')

  const summaryQuery = usePortfolioSummary()
  const positionsQuery = usePortfolioPositions()

  const summary = summaryQuery.data
  const positions = positionsQuery.data ?? []

  const totalInvested = 41482.4
  const totalCurrent = 39469.2
  const totalResultPercent = -4.85
  const totalResultRub = -2013.3

  return (
    <div className="space-y-8">
      {/* Header + Tabs */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Портфель</h1>
        <p className="text-slate-400 mt-1">Обзор и анализ вашего инвестиционного портфеля</p>

        {/* Tabs */}
        <div className="flex gap-8 mt-6 border-b border-slate-800">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-4 text-sm font-medium transition-colors relative ${
                activeTab === tab
                  ? 'text-white after:absolute after:bottom-0 after:left-0 after:h-0.5 after:w-full after:bg-blue-500'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Основные показатели */}
      <GlassCard>
        <div className="p-6">
          <SectionHeader title="Основные показатели" />

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mt-8">
            <div>
              <p className="text-sm text-slate-400">Вложено</p>
              <p className="text-3xl font-bold mt-2">{totalInvested.toLocaleString('ru-RU')} ₽</p>
            </div>

            <div>
              <p className="text-sm text-slate-400">Сейчас</p>
              <p className="text-3xl font-bold mt-2">{totalCurrent.toLocaleString('ru-RU')} ₽</p>
            </div>

            <div>
              <p className="text-sm text-slate-400">Результат</p>
              <div className="flex items-center gap-3 mt-2">
                <p className={`text-3xl font-bold ${totalResultPercent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {totalResultPercent}%
                </p>
                <p className={`text-xl ${totalResultPercent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {totalResultRub.toLocaleString('ru-RU')} ₽
                </p>
              </div>
            </div>

            <div>
              <p className="text-sm text-slate-400">Доход на 12М</p>
              <p className="text-3xl font-bold mt-2 text-emerald-400">2 808,8 ₽</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 mt-10 pt-8 border-t border-slate-800">
            <div>
              <p className="text-sm text-slate-400">Рыночная доходность за 12М</p>
              <p className="text-2xl font-semibold mt-1">7,1%</p>
            </div>
            <div>
              <p className="text-sm text-slate-400">Ваша доходность за 12М</p>
              <p className="text-2xl font-semibold mt-1">6,8%</p>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Ближайшие выплаты */}
      <GlassCard>
        <div className="p-6">
          <SectionHeader
            title="Ближайшие выплаты"
            action={<Calendar className="h-5 w-5 text-slate-400" />}
          />

          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-slate-800 text-left text-sm text-slate-400">
                  <th className="pb-4 font-medium">Компания</th>
                  <th className="pb-4 font-medium">Выплата</th>
                  <th className="pb-4 font-medium">Статус</th>
                  <th className="pb-4 font-medium text-right">Доход</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-sm">
                {[
                  { company: 'Татнефть TATN', date: '29 июл 2026', status: 'объявлено', income: '10,1 ₽' },
                  { company: 'Сбербанк SBER', date: '3 авг 2026', status: 'объявлено', income: '2 619,7 ₽' },
                  { company: 'Яндекс YDEX', date: '13 окт 2026', status: 'прогноз', income: '162,2 ₽' },
                  { company: 'Татнефть TATN', date: '28 окт 2026', status: 'прогноз', income: '16,76 ₽' },
                ].map((item, i) => (
                  <tr key={i} className="hover:bg-slate-900/50">
                    <td className="py-4 font-medium">{item.company}</td>
                    <td className="py-4 text-slate-400">{item.date}</td>
                    <td className="py-4">
                      <span className="px-3 py-1 rounded-full bg-slate-800 text-xs">
                        {item.status}
                      </span>
                    </td>
                    <td className="py-4 text-right font-medium">{item.income}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </GlassCard>

      {/* Блоки с распределением */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Структура дохода */}
        <GlassCard>
          <div className="p-6">
            <SectionHeader title="Структура дохода" />
              <div className="mt-8 flex justify-center">
              <DonutChart
                data={[
                  { name: 'Финансы', value: 3000 },
                ]}
                value="value"
                category="name"
                colors={[
                  "blue",
                ]}
                className="h-72 w-72"
                showTooltip
                showLabel
              />
            </div>
            <div className="mt-8 flex flex-col gap-6">
              <div className="flex justify-between items-center">
                <div>
                  <p className="font-medium">Дивиденды</p>
                  <p className="text-sm text-slate-400">100% дохода</p>
                </div>
                <p className="text-2xl font-bold">3К ₽</p>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Распределение по активам */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Круговая диаграмма */}
          <GlassCard className="lg:col-span-2">
            <div className="p-6">
              <SectionHeader title="Распределение по активам" />
              <div className="mt-8 flex justify-center">
                <DonutChart
                  data={[
                    { name: 'Сбербанк', value: 65.3 },
                    { name: 'Яндекс', value: 20.2 },
                    { name: 'ВК', value: 11.3 },
                    { name: 'Северсталь', value: 1.7 },
                    { name: 'Татнефть', value: 1.5 },
                  ]}
                  value="value"
                  category="name"
                  colors={[
                    "blue",
                    "cyan",
                    "violet",
                    "amber",
                    "emerald",
                  ]}
                  className="h-72 w-72"
                  showTooltip
                  showLabel
                />
              </div>
            </div>
            <div className="p-6">
              <div className="mt-6 space-y-6">
                {[
                  { name: 'Сбербанк', percent: 65.3, color: 'bg-blue-500' },
                  { name: 'Яндекс', percent: 20.2, color: 'bg-cyan-500' },
                  { name: 'ВК', percent: 11.3, color: 'bg-violet-500' },
                  { name: 'Северсталь', percent: 1.7, color: 'bg-amber-500' },
                  { name: 'Татнефть', percent: 1.5, color: 'bg-emerald-500' },
                ].map((asset) => (
                  <div key={asset.name}>
                    <div className="flex justify-between text-sm mb-2">
                      <span className="font-medium">{asset.name}</span>
                      <span className="font-semibold text-white">{asset.percent}%</span>
                    </div>
                    <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${asset.color} rounded-full transition-all`}
                        style={{ width: `${asset.percent}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </GlassCard>
        </div>
      </div>

      {/* Распределение по секторам */}
      <GlassCard>
        <div className="p-6">
          <SectionHeader title="Распределение по секторам" />
          <div className="mt-8 flex justify-center">
            <DonutChart
              data={[
                { name: 'Финансы', value: 65.3 },
                { name: 'Технологии', value: 31.4 },
                { name: 'Добыча металлов', value: 1.7 },
                { name: 'Нефть и газ', value: 1.5 },
              ]}
              value="value"
              category="name"
              colors={[
                "blue",
                "cyan",
                "violet",
                "amber",
                "emerald",
              ]}
              className="h-72 w-72"
              showTooltip
              showLabel
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-8">
            {[
              { sector: 'Финансы', percent: 65.3 },
              { sector: 'Технологии', percent: 31.4 },
              { sector: 'Добыча металлов', percent: 1.7 },
              { sector: 'Нефть и газ', percent: 1.5 },
            ].map((item) => (
              <div key={item.sector} className="text-center">
                <div className="text-4xl font-bold text-white">{item.percent}%</div>
                <p className="text-slate-400 mt-2">{item.sector}</p>
              </div>
            ))}
          </div>
        </div>
      </GlassCard>
    </div>
  )
}
