import { useState } from 'react'
import { Send, Sparkles } from 'lucide-react'

import { Input } from '@/shared/ui/input'
import { Button } from '@/shared/ui/button'
import { GlassCard } from '@/shared/ui'

import { mockAICopilotHistory } from '@/shared/mock/mock-data'

export function AIChatPage() {
  const [messages, setMessages] = useState(mockAICopilotHistory)
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const userMsg = {
      id: `msg-${Date.now()}`,
      role: 'user' as const,
      message: inputValue,
    }

    setMessages((prev) => [...prev, userMsg])
    const currentInput = inputValue
    setInputValue('')
    setIsLoading(true)

    // TODO: Здесь будет реальный вызов AI API
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          role: 'assistant' as const,
          message: 'Это тестовый ответ. Замените на реальный ответ от ИИ.',
        },
      ])
      setIsLoading(false)
    }, 1200)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Sparkles className="h-9 w-9 text-blue-400" />
            Терминал ИИ
          </h1>
          <p className="text-slate-400 mt-1 text-lg">
            Ваш персональный AI-помощник для анализа рынка
          </p>
        </div>
      </div>

      {/* Chat Container */}
      <GlassCard className="flex-1 flex flex-col overflow-hidden border border-slate-700/50">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="mb-8">
                <Sparkles className="h-20 w-20 text-slate-600 mx-auto" />
              </div>
              <h3 className="text-2xl font-medium text-slate-200 mb-3">
                Как я могу помочь сегодня?
              </h3>
              <p className="text-slate-400 max-w-md">
                Задайте вопрос о рынке, портфеле, техническом анализе или конкретном инструменте
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] md:max-w-[75%] px-6 py-4 rounded-3xl ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-800/90 border border-slate-700/70 text-slate-100'
                  }`}
                >
                  <p className="text-[15.5px] leading-relaxed whitespace-pre-wrap">
                    {msg.message}
                  </p>
                </div>
              </div>
            ))
          )}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-slate-800/90 border border-slate-700/70 px-6 py-4 rounded-3xl">
                <div className="flex gap-1.5">
                  <div className="h-2 w-2 rounded-full bg-slate-400 animate-bounce" />
                  <div className="h-2 w-2 rounded-full bg-slate-400 animate-bounce delay-150" />
                  <div className="h-2 w-2 rounded-full bg-slate-400 animate-bounce delay-300" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-700/50 p-6 bg-slate-950/50">
          <div className="flex gap-3">
            <Input
              placeholder="Спросите о BTC, SBER, портфеле или рынке..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSendMessage()
                }
              }}
              className="flex-1 bg-slate-900 border-slate-700 text-white placeholder:text-slate-500 py-6 text-base rounded-2xl"
              disabled={isLoading}
            />
            <Button
              onClick={handleSendMessage}
              disabled={isLoading || !inputValue.trim()}
              size="icon"
              className="h-14 w-14 rounded-2xl shrink-0"
            >
              <Send className="h-6 w-6" />
            </Button>
          </div>
          <p className="text-center text-xs text-slate-500 mt-3">
            AI может ошибаться. Проверяйте важные решения.
          </p>
        </div>
      </GlassCard>
    </div>
  )
}
