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
from typing import Any, Optional, cast

import pandas as pd

from swingtraderai.backtesting.config import BacktestConfig, EntryMode
from swingtraderai.backtesting.metrics import calculate_metrics
from swingtraderai.backtesting.models import (
	BacktestResult,
	EquityPoint,
	Side,
)
from swingtraderai.backtesting.position_manager import PositionManager
from swingtraderai.backtesting.signal_generator import SignalGenerator


class BacktestEngine:
	def __init__(
		self,
		config: Optional[BacktestConfig] = None,
		signal_generator: Optional[Any] = None,
	) -> None:
		self.config = config or BacktestConfig()
		self.signal_gen = signal_generator or SignalGenerator(self.config)

	def run(
		self,
		df: pd.DataFrame,
		ticker: str = "UNKNOWN",
		timeframe: str = "1h",
		start: Optional[pd.Timestamp] = None,
		end: Optional[pd.Timestamp] = None,
		trade_start: Optional[pd.Timestamp] = None,
		trade_end: Optional[pd.Timestamp] = None,
	) -> BacktestResult:
		"""Run a single-ticker backtest.

		Parameters
		----------
		df : DataFrame
			Must contain columns: time, open, high, low, close, volume
			(case-insensitive). Must be sorted ascending by time.
		ticker, timeframe :
			Labels stored on signals / trades.
		start, end :
			Optional hard filters on the dataframe (rows outside are dropped).
		trade_start, trade_end :
			Optional trading window. History *before* trade_start is kept for
			warmup / features, but new entries are only queued inside the window.
			Open positions may still exit after trade_end (managed until flat
			or data end). Use this for walk-forward test segments.
		"""
		df = self._prepare(df, start, end)
		if len(df) <= self.config.warmup_bars:
			raise ValueError(
				f"Not enough bars ({len(df)}) for warmup_bars={self.config.warmup_bars}"
			)

		ts_trade_start = pd.Timestamp(trade_start) if trade_start is not None else None
		ts_trade_end = pd.Timestamp(trade_end) if trade_end is not None else None

		pm = PositionManager(self.config)
		signals_count = 0
		equity_curve: list[EquityPoint] = []

		n = len(df)
		for i in range(self.config.warmup_bars, n):
			row = df.iloc[i]
			bar_time = self._to_datetime(row["time"])
			bar_ts = pd.Timestamp(bar_time)
			open, high, low, close = (
				float(row["open"]),
				float(row["high"]),
				float(row["low"]),
				float(row["close"]),
			)

			in_trade_window = True
			if ts_trade_start is not None and bar_ts < ts_trade_start:
				in_trade_window = False
			if ts_trade_end is not None and bar_ts > ts_trade_end:
				in_trade_window = False

			# 1–2. Point-in-time history & signal (known at close of this bar)
			history = df.iloc[: i + 1]
			signal = self.signal_gen.generate(
				history=history,
				ticker=ticker,
				timeframe=timeframe,
				bar_timestamp=bar_time,
			)
			signals_count += 1

			# 3. Fill pending entry only inside / at trade window
			#    (pending from last bar of window is still filled)
			if self.config.entry_mode == EntryMode.NEXT_OPEN:
				if in_trade_window or (
					ts_trade_start is not None and bar_ts >= ts_trade_start
				):
					# Allow fill if we are at or after trade_start
					if ts_trade_end is None or bar_ts <= ts_trade_end:
						pm.try_fill_pending_entry(
							bar_open=open, bar_time=bar_time, bar_index=i
						)
					else:
						pm.pending_entry = None
				else:
					pm.pending_entry = None

			# 4. Manage open position on this bar's OHLC (always, if open)
			pm.update_on_bar(
				bar_open=open,
				bar_high=high,
				bar_low=low,
				bar_close=close,
				bar_time=bar_time,
				signal=signal if in_trade_window else None,
			)

			# 5. Queue new entry only inside trade window
			if in_trade_window and pm.position is None and signal.side != Side.NEUTRAL:
				if self.config.entry_mode == EntryMode.NEXT_OPEN:
					pm.queue_entry(signal)
				elif self.config.entry_mode == EntryMode.CURRENT_CLOSE:
					pm.queue_entry(signal)
					pm.try_fill_pending_entry(
						bar_open=close, bar_time=bar_time, bar_index=i
					)

			# 6. Mark-to-market (record only inside trade window for clean curves)
			if in_trade_window or pm.position is not None:
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

		start_ts = self._to_datetime(df.iloc[self.config.warmup_bars]["time"])
		metrics = calculate_metrics(
			trades=pm.closed_trades,
			equity_curve=equity_curve,
			initial_capital=self.config.initial_capital,
			start=start_ts,
			end=last_time,
		)

		return BacktestResult(
			ticker=ticker,
			timeframe=timeframe,
			start=start_ts,
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
