"""Базовые стратегии для сравнения с конвейером обработки составных сигналов.

Ответ базовых стратегий:
добавляет ли сложная система ценность по сравнению с тривиальными правилами?

1. Покупка и удержание
2. Простое пересечение SMA
3. Только составной сигнал (существующий SignalGenerator, use_ml=False)
4. Составной сигнал + машинное обучение (Фаза 4 — заглушка здесь)

Каждая базовая стратегия предоставляет
``generate(history, ticker, timeframe, bar_timestamp)``,
совместимый с интерфейсом SignalGenerator движка, поэтому используется тот же
путь исполнения / затрат / метрик.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from swingtraderai.backtesting.config import BacktestConfig
from swingtraderai.backtesting.models import Side, Signal
from swingtraderai.backtesting.signal_generator import (
	SignalGenerator,
	_default_sl_tp,
	_simple_atr,
)


class BuyAndHoldGenerator:
	"""Нажимайте кнопку "долго" на первой доступной полосе,
	удерживайте ее бесконечно (выход через сигнал невозможен)."""

	def __init__(self, config: BacktestConfig) -> None:
		self.config = config
		self._entered = False

	def generate(
		self,
		history: pd.DataFrame,
		ticker: str,
		timeframe: str,
		bar_timestamp: datetime,
	) -> Signal:
		hist = history.copy()
		hist.columns = [c.lower() for c in hist.columns]
		close = float(hist["close"].iloc[-1]) if len(hist) else 0.0

		if not self._entered and len(hist) >= max(1, self.config.warmup_bars):
			self._entered = True
			atr = _simple_atr(hist)
			# Wide SL so B&H is not stopped out by noise; no TP
			sl, _ = _default_sl_tp(close, Side.LONG, self.config, atr=atr)
			return Signal(
				timestamp=bar_timestamp,
				ticker=ticker,
				timeframe=timeframe,
				side=Side.LONG,
				signal_type="BUY",
				signal_score=10.0,
				entry_reference_price=close,
				stop_loss=None,  # hold through
				take_profit=None,
				market_regime="buy_hold",
			)

		return Signal(
			timestamp=bar_timestamp,
			ticker=ticker,
			timeframe=timeframe,
			side=Side.NEUTRAL,
			signal_type="NEUTRAL",
			signal_score=1.0,
			entry_reference_price=close,
			market_regime="buy_hold",
		)


class SMACrossoverGenerator:
	"""Длинная линия, когда быстрая СМА пересекает линию выше медленной СМА,
	плоская/короткая линия, когда пересекает линию ниже."""

	def __init__(
		self,
		config: BacktestConfig,
		fast: int = 10,
		slow: int = 30,
		allow_short: Optional[bool] = None,
	) -> None:
		self.config = config
		self.fast = fast
		self.slow = slow
		self.allow_short = config.allow_short if allow_short is None else allow_short

	def generate(
		self,
		history: pd.DataFrame,
		ticker: str,
		timeframe: str,
		bar_timestamp: datetime,
	) -> Signal:
		hist = history.copy()
		hist.columns = [c.lower() for c in hist.columns]
		close = hist["close"].astype(float)
		px = float(close.iloc[-1]) if len(close) else 0.0

		if len(close) < self.slow + 1:
			return Signal(
				timestamp=bar_timestamp,
				ticker=ticker,
				timeframe=timeframe,
				side=Side.NEUTRAL,
				signal_type="NEUTRAL",
				signal_score=1.0,
				entry_reference_price=px,
				market_regime="sma_cross",
			)

		fast_sma = close.rolling(self.fast).mean()
		slow_sma = close.rolling(self.slow).mean()
		f0, f1 = float(fast_sma.iloc[-2]), float(fast_sma.iloc[-1])
		s0, s1 = float(slow_sma.iloc[-2]), float(slow_sma.iloc[-1])

		side = Side.NEUTRAL
		signal_type = "NEUTRAL"
		score = 1.0

		# Bullish cross
		if f0 <= s0 and f1 > s1:
			side = Side.LONG
			signal_type = "BUY"
			score = 7.0
		# Bearish cross
		elif f0 >= s0 and f1 < s1:
			if self.allow_short:
				side = Side.SHORT
				signal_type = "SELL"
				score = 7.0
			else:
				# Exit-only signal for long-only engines (signal reverse)
				side = Side.SHORT  # position_manager treats as reverse
				signal_type = "SELL"
				score = 7.0

		atr = _simple_atr(hist)
		sl, tp = _default_sl_tp(px, side, self.config, atr=atr)

		return Signal(
			timestamp=bar_timestamp,
			ticker=ticker,
			timeframe=timeframe,
			side=side,
			signal_type=signal_type,
			signal_score=score,
			entry_reference_price=px,
			stop_loss=sl,
			take_profit=tp,
			market_regime="sma_cross",
		)


class CompositeBaselineGenerator(SignalGenerator):
	"""Существующий составной конвейер с принудительно отключенной функцией use_ml."""

	def __init__(self, config: BacktestConfig) -> None:
		cfg = config.model_copy(update={"use_ml": False})
		super().__init__(cfg)


def make_baseline(name: str, config: BacktestConfig) -> object:
	"""Factory: 'buy_hold' | 'sma_cross' | 'composite'."""
	key = name.lower().strip()
	if key in ("buy_hold", "buyandhold", "bh"):
		return BuyAndHoldGenerator(config)
	if key in ("sma_cross", "sma", "ma_cross"):
		return SMACrossoverGenerator(config)
	if key in ("composite", "signal", "composite_signal"):
		return CompositeBaselineGenerator(config)
	raise ValueError(f"Unknown baseline: {name!r}")
