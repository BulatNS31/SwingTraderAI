"""Детерминированный источник сигналов для синтетических регрессионных тестов.

Позволяет внедрять предопределенную последовательность сторон,
обозначенных индексом бара, чтобы исполнение/учет
можно было проверить вручную, не полагаясь на RSI/EMA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import pandas as pd

from swingtraderai.backtesting.config import BacktestConfig
from swingtraderai.backtesting.models import Side, Signal
from swingtraderai.backtesting.signal_generator import _default_sl_tp, _simple_atr


class ForcedSignalGenerator:
	"""На карте bar_index → ​​Сторона. Отсутствующие индексы → НЕЙТРАЛЬНО.

	bar_index - индекс внутри *полного* датафрейма,
	передаваемого в движок (включая предварительную настройку).
	Генератор получает историю = df[:i+1],
	вообщем bar_index == len(history) - 1.
	"""

	def __init__(
		self,
		config: BacktestConfig,
		schedule: Dict[int, Side],
		signal_score: float = 8.0,
	) -> None:
		self.config = config
		self.schedule = schedule
		self.signal_score = signal_score

	def generate(
		self,
		history: pd.DataFrame,
		ticker: str,
		timeframe: str,
		bar_timestamp: datetime,
	) -> Signal:
		hist = history.copy()
		hist.columns = [c.lower() for c in hist.columns]
		bar_index = len(hist) - 1
		close = float(hist["close"].iloc[-1])
		side = self.schedule.get(bar_index, Side.NEUTRAL)

		if side == Side.NEUTRAL:
			return Signal(
				timestamp=bar_timestamp,
				ticker=ticker,
				timeframe=timeframe,
				side=Side.NEUTRAL,
				signal_type="NEUTRAL",
				signal_score=1.0,
				entry_reference_price=close,
			)

		atr = _simple_atr(hist)
		sl, tp = _default_sl_tp(close, side, self.config, atr=atr)
		signal_type = "BUY" if side == Side.LONG else "SELL"

		return Signal(
			timestamp=bar_timestamp,
			ticker=ticker,
			timeframe=timeframe,
			side=side,
			signal_type=signal_type,
			signal_score=self.signal_score,
			entry_reference_price=close,
			stop_loss=sl,
			take_profit=tp,
		)
