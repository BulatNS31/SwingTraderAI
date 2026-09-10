"""Базовый бэктестер.

Порядок обработки баров (фиксированный, без опережающего анализа):

Для каждого бара T (индекс i >= warmup):
1. history = df.iloc[: i+1] # только данные, известные на момент закрытия бара T
2. signal  = SignalGenerator(history)
3. если есть отложенная сделка с T-1 → исполнение при открытии бара T
4. управление открытой позицией (SL/TP/трейлинг/тайминг) на баре T OHLC
5. если позиции нет и сигнал применим → очередь на открытие сделки на T+1
6. рыночная оценка эквити на момент закрытия бара T
7. запись точки эквити

Сигнал, генерируемый на момент закрытия бара T,
никогда не использует данные после бара T.
Исполнение этого сигнала происходит при открытии бара T+1.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, cast

import pandas as pd

from .config import BacktestConfig, EntryMode
from .models import (
	BacktestMetrics,
	BacktestResult,
	EquityPoint,
	Side,
	Trade,
)
from .position_manager import PositionManager
from .signal_generator import SignalGenerator


class BacktestEngine:
	def __init__(self, config: Optional[BacktestConfig] = None) -> None:
		self.config = config or BacktestConfig()
		self.signal_gen = SignalGenerator(self.config)

	def run(
		self,
		df: pd.DataFrame,
		ticker: str = "UNKNOWN",
		timeframe: str = "1h",
		start: Optional[pd.Timestamp] = None,
		end: Optional[pd.Timestamp] = None,
	) -> BacktestResult:
		"""Run a single-ticker backtest.

		Parameters
		----------
		df : DataFrame
		Must contain columns: time, open, high, low, close, volume
		(case-insensitive). Must be sorted ascending by time.
		ticker, timeframe :
		Labels stored on signals / trades.
		start, end:
		Optional time filters applied after warmup.
		"""
		df = self._prepare(df, start, end)
		if len(df) <= self.config.warmup_bars:
			raise ValueError(
				f"Not enough bars ({len(df)}) for warmup_bars={self.config.warmup_bars}"
			)

		pm = PositionManager(self.config)
		signals_count = 0
		equity_curve: list[EquityPoint] = []

		n = len(df)
		for i in range(self.config.warmup_bars, n):
			row = df.iloc[i]
			bar_time = self._to_datetime(row["time"])
			open, _, _, close = (
				float(row["open"]),
				float(row["high"]),
				float(row["low"]),
				float(row["close"]),
			)

			# 1–2. Point-in-time history & signal (known at close of this bar)
			history = df.iloc[: i + 1]
			signal = self.signal_gen.generate(
				history=history,
				ticker=ticker,
				timeframe=timeframe,
				bar_timestamp=bar_time,
			)
			signals_count += 1

			# 3. Fill any pending entry from previous bar's signal (next_open)
			if self.config.entry_mode == EntryMode.NEXT_OPEN:
				pm.try_fill_pending_entry(bar_open=open, bar_time=bar_time, bar_index=i)

			# 4. Manage open position on this bar's OHLC
			# closed = pm.update_on_bar(
			# 	bar_open=open,
			# 	bar_high=high,
			# 	bar_low=low,
			# 	bar_close=close,
			# 	bar_time=bar_time,
			# 	signal=signal,
			# )
			# closed trade is already stored inside pm

			# 5. Queue new entry if flat and signal is actionable
			if pm.position is None and signal.side != Side.NEUTRAL:
				if self.config.entry_mode == EntryMode.NEXT_OPEN:
					pm.queue_entry(signal)
				elif self.config.entry_mode == EntryMode.CURRENT_CLOSE:
					# Explicit opt-in: fill at this bar's close
					pm.queue_entry(signal)
					pm.try_fill_pending_entry(
						bar_open=close, bar_time=bar_time, bar_index=i
					)

			# 6. Mark-to-market
			equity = pm.mark_to_market(close)
			equity_curve.append(
				EquityPoint(
					time=bar_time,
					equity=equity,
					cash=pm.cash,
					unrealized_pnl=(
						pm.position.unrealized_pnl(close) if pm.position else 0.0
					),
					drawdown=pm.current_drawdown,
					drawdown_pct=pm.current_drawdown_pct,
				)
			)

		# End-of-data forced close
		last = df.iloc[-1]
		last_time = self._to_datetime(last["time"])
		pm.close_all(float(last["close"]), last_time)
		# Final equity point already recorded; update last if needed
		if equity_curve:
			equity_curve[-1] = EquityPoint(
				time=last_time,
				equity=pm.mark_to_market(float(last["close"])),
				cash=pm.cash,
				unrealized_pnl=0.0,
				drawdown=pm.current_drawdown,
				drawdown_pct=pm.current_drawdown_pct,
			)

		metrics = self._basic_metrics(pm.closed_trades, equity_curve)

		return BacktestResult(
			ticker=ticker,
			timeframe=timeframe,
			start=self._to_datetime(df.iloc[self.config.warmup_bars]["time"]),
			end=last_time,
			config=self.config,
			trades=pm.closed_trades,
			equity_curve=equity_curve,
			metrics=metrics,
			model_version=self.config.model_version,
			bars_processed=n - self.config.warmup_bars,
			signals_generated=signals_count,
			notes=self.config.notes,
		)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _prepare(
		self,
		df: pd.DataFrame,
		start: Optional[pd.Timestamp],
		end: Optional[pd.Timestamp],
	) -> pd.DataFrame:
		out = df.copy()
		out.columns = [c.lower() for c in out.columns]
		required = {"time", "open", "high", "low", "close"}
		missing = required - set(out.columns)
		if missing:
			raise ValueError(f"Missing required columns: {missing}")

		out["time"] = pd.to_datetime(out["time"])
		out = out.sort_values("time").reset_index(drop=True)

		if start is not None:
			out = out[out["time"] >= pd.Timestamp(start)]
		if end is not None:
			out = out[out["time"] <= pd.Timestamp(end)]
		out = out.reset_index(drop=True)
		return out

	@staticmethod
	def _to_datetime(value: object) -> datetime:
		if isinstance(value, datetime):
			return value

		ts = pd.to_datetime(value)

		if isinstance(ts, pd.Timestamp):
			return cast(datetime, ts.to_pydatetime())

		raise TypeError(f"Cannot convert {type(value).__name__} to datetime")

	def _basic_metrics(
		self, trades: List[Trade], equity_curve: List[EquityPoint]
	) -> BacktestMetrics:
		"""Minimal metrics for Phase 1. Full set arrives in Phase 2."""
		m = BacktestMetrics()
		m.total_trades = len(trades)
		if not trades:
			if equity_curve:
				m.total_return = equity_curve[-1].equity - self.config.initial_capital
				m.total_return_pct = (
					m.total_return / self.config.initial_capital
				) * 100.0
			return m

		pnls = [t.pnl for t in trades]
		wins = [p for p in pnls if p > 0]
		losses = [p for p in pnls if p <= 0]
		m.winning_trades = len(wins)
		m.losing_trades = len(losses)
		m.win_rate = m.winning_trades / m.total_trades if m.total_trades else 0.0
		m.loss_rate = 1.0 - m.win_rate
		m.average_trade = sum(pnls) / m.total_trades
		m.average_win = sum(wins) / len(wins) if wins else 0.0
		m.average_loss = sum(losses) / len(losses) if losses else 0.0
		m.largest_win = max(pnls)
		m.largest_loss = min(pnls)
		m.average_bars_held = sum(t.bars_held for t in trades) / m.total_trades
		m.avg_mfe = sum(t.max_favorable_excursion for t in trades) / m.total_trades
		m.avg_mae = sum(t.max_adverse_excursion for t in trades) / m.total_trades

		gross_profit = sum(wins) if wins else 0.0
		gross_loss = abs(sum(losses)) if losses else 0.0
		m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
		m.expectancy = m.average_trade

		if equity_curve:
			final_eq = equity_curve[-1].equity
			m.total_return = final_eq - self.config.initial_capital
			m.total_return_pct = (m.total_return / self.config.initial_capital) * 100.0
			m.max_drawdown = max(ep.drawdown for ep in equity_curve)
			m.max_drawdown_pct = max(ep.drawdown_pct for ep in equity_curve)

		return m
