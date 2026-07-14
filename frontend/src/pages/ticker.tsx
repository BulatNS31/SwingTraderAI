import React from 'react';
import { useParams } from 'react-router-dom'
import TickerWorkspace from '../features/tickers/components/ticker-workspace';

export function TickerPage(): React.ReactNode {
  const { symbol } = useParams<{ symbol: string }>()

  if (!symbol) {
    return <div>Тикер не найден</div>
  }

  return (
    <TickerWorkspace symbol={symbol} />
  );
};
