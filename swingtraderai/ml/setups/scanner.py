from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import pandas as pd

from swingtraderai.indicators.bsu_bpu_levels import detect_bsu_bpu_levels
from swingtraderai.indicators.matrix import add_all_indicators
from swingtraderai.indicators.momentum.divergence import detect_divergences
from swingtraderai.ml.setups.builders.bsu_bpu import build_bsu_bpu_setups
from swingtraderai.ml.setups.builders.divergence import build_divergence_setups
from swingtraderai.ml.setups.builders.false_breakout import build_false_breakout_setups
from swingtraderai.ml.setups.trend import detect_trend
from swingtraderai.ml.trainer import detect_false_breakout, detect_strong_levels
from swingtraderai.schemas.trade_setup import TradeSetup, TradeSetupList


class SetupScanner:
	"""
	Детерминированный сканер торговых сценариев.

	Не использует ML и LLM — только pandas + твои детекторы.
	"""

	def __init__(
		self,
		*,
		use_divergence: bool = True,
		use_false_breakout: bool = True,
		use_bsu_bpu: bool = True,
		require_trend_align: bool = True,
		only_last_bar: bool = True,
	) -> None:
		self.use_divergence = use_divergence
		self.use_false_breakout = use_false_breakout
		self.use_bsu_bpu = use_bsu_bpu
		self.require_trend_align = require_trend_align
		self.only_last_bar = only_last_bar

	def prepare(self, df: pd.DataFrame, timeframe: str = "1D") -> pd.DataFrame:
		"""Индикаторы + уровни + триггеры. Можно вызывать отдельно для тестов."""
		out = df.copy()
		out.columns = [str(c).lower() for c in out.columns]

		if "timeframe" not in out.columns:
			out["timeframe"] = timeframe

		out = add_all_indicators(out, timeframe=timeframe)

		# volume helpers if missing
		if "volume" in out.columns and "volume_ratio" not in out.columns:
			out["volume_ratio"] = out["volume"] / out["volume"].rolling(30).mean()

		out = detect_strong_levels(out, min_tests=2, window=100)
		out = detect_false_breakout(out, min_depth_atr=0.4)

		if detect_bsu_bpu_levels is not None:
			bsu = detect_bsu_bpu_levels(out)
			out = pd.concat([out, bsu], axis=1)

		if detect_divergences is not None:
			div_rsi = detect_divergences(out, oscillator_type="rsi")
			out = pd.concat([out, div_rsi], axis=1)
			div_macd = detect_divergences(out, oscillator_type="macd")
			div_macd = div_macd.rename(
				columns={
					"bullish_divergence": "bullish_divergence_macd",
					"bearish_divergence": "bearish_divergence_macd",
					"oscillator_value": "macd_hist_div",
				}
			)
			out = pd.concat([out, div_macd], axis=1)

		return out

	def scan(
		self,
		df: pd.DataFrame,
		*,
		symbol: str,
		timeframe: str = "1D",
		ticker_id: Optional[UUID] = None,
		prepare: bool = True,
	) -> TradeSetupList:
		work = self.prepare(df, timeframe=timeframe) if prepare else df.copy()
		trend = detect_trend(work)

		setups: List[TradeSetup] = []

		if self.use_divergence and detect_divergences is not None:
			setups.extend(
				build_divergence_setups(
					work,
					symbol=symbol,
					timeframe=timeframe,
					trend=trend,
					ticker_id=ticker_id,
					only_last_bar=self.only_last_bar,
					require_trend_align=self.require_trend_align,
				)
			)

		if self.use_false_breakout:
			setups.extend(
				build_false_breakout_setups(
					work,
					symbol=symbol,
					timeframe=timeframe,
					trend=trend,
					ticker_id=ticker_id,
					only_last_bar=self.only_last_bar,
					require_trend_align=self.require_trend_align,
				)
			)

		if self.use_bsu_bpu and detect_bsu_bpu_levels is not None:
			setups.extend(
				build_bsu_bpu_setups(
					work,
					symbol=symbol,
					timeframe=timeframe,
					trend=trend,
					ticker_id=ticker_id,
					only_last_bar=self.only_last_bar,
				)
			)

		as_of = datetime.now(timezone.utc)
		if "time" in work.columns and len(work):
			t = work.iloc[-1]["time"]
			as_of = t if isinstance(t, datetime) else pd.to_datetime(t).to_pydatetime()

		return TradeSetupList(
			symbol=symbol,
			timeframe=timeframe,
			as_of=as_of,
			setups=setups,
		)
