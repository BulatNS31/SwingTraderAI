from typing import Any

import pandas as pd
import pandas_ta as pdt

from ..base import BaseIndicator, IndicatorResult
from ..registry import registry


class RSIIndicator(BaseIndicator):
	name = "rsi"
	category = "momentum"
	description = "Relative Strength Index (14)"

	def __init__(self, name: str = "rsi", length: int = 14):
		self.name = name
		self.length = length
		self.category = "momentum"
		self.description = f"Relative Strength Index ({length})"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		length = kwargs.get("length", self.length)

		if df.empty or len(df) < length or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		rsi = pdt.rsi(df["close"], length=length)
		latest = rsi.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"length": length},
		)


class MACDIndicator(BaseIndicator):
	name = "macd"
	category = "momentum"
	description = "Moving Average Convergence Divergence"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		if df.empty or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		macd = pdt.macd(df["close"])
		if macd is None or macd.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "insufficient_data", "min_required_rows": 33},
			)

		latest = macd.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value={
				"macd": (
					float(latest["MACD_12_26_9"])
					if pd.notna(latest["MACD_12_26_9"])
					else None
				),
				"signal": (
					float(latest["MACDs_12_26_9"])
					if pd.notna(latest["MACDs_12_26_9"])
					else None
				),
				"histogram": (
					float(latest["MACDh_12_26_9"])
					if pd.notna(latest["MACDh_12_26_9"])
					else None
				),
			},
			metadata={"type": "macd"},
		)


class StochasticIndicator(BaseIndicator):
	name = "stoch"
	category = "momentum"
	description = "Stochastic Oscillator (%K and %D)"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		if (
			df.empty
			or len(df) < 14
			or not all(col in df.columns for col in ["high", "low", "close"])
		):
			return IndicatorResult(name=self.name, value=None)

		stoch = pdt.stoch(df["high"], df["low"], df["close"], k=14, d=3)
		latest = stoch.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value={
				"k": (
					float(latest["STOCHk_14_3_3"])
					if pd.notna(latest.get("STOCHk_14_3_3"))
					else None
				),
				"d": (
					float(latest["STOCHd_14_3_3"])
					if pd.notna(latest.get("STOCHd_14_3_3"))
					else None
				),
			},
			metadata={"type": "stochastic"},
		)


class CCIIndicator(BaseIndicator):
	name = "cci"
	category = "momentum"
	description = "Commodity Channel Index"

	def __init__(self, name: str = "cci", length: int = 20):
		self.name = name
		self.length = length
		self.category = "momentum"
		self.description = f"Commodity Channel Index ({length})"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		length = kwargs.get("length", self.length)

		if (
			df.empty
			or len(df) < length
			or not all(col in df.columns for col in ["high", "low", "close"])
		):
			return IndicatorResult(name=self.name, value=None)

		cci = pdt.cci(df["high"], df["low"], df["close"], length=length)
		latest = cci.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"length": length},
		)


registry.register(RSIIndicator())
registry.register(RSIIndicator(name="rsi7", length=7))
registry.register(RSIIndicator(name="rsi14", length=14))

registry.register(MACDIndicator())
registry.register(StochasticIndicator())
registry.register(CCIIndicator())
registry.register(CCIIndicator(name="cci14", length=14))
