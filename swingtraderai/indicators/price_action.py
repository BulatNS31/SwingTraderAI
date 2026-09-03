from typing import Any

import numpy as np
import pandas as pd
import pandas_ta as pdt

from .base import BaseIndicator, IndicatorResult
from .registry import registry


class ReturnsIndicator(BaseIndicator):
	name = "returns"
	category = "price_action"
	description = "Percentage Change (Returns)"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		if df.empty or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		returns = df["close"].pct_change() * 100
		latest = returns.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"unit": "%"},
		)


class LogReturnsIndicator(BaseIndicator):
	name = "log_returns"
	category = "price_action"
	description = "Logarithmic Returns"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		if df.empty or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		log_returns = np.log(df["close"] / df["close"].shift(1))
		latest = log_returns.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"unit": "log"},
		)


class MomentumIndicator(BaseIndicator):
	name = "momentum"
	category = "price_action"
	description = "Price Momentum (Close - Close_n)"

	def __init__(self, name: str = "momentum", period: int = 10):
		self.name = name
		self.period = period
		self.description = f"Price Momentum ({period} periods)"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		period = kwargs.get("period", self.period)

		if df.empty or len(df) < period or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		momentum = df["close"] - df["close"].shift(period)
		latest = momentum.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"period": period},
		)


class ZScorePriceIndicator(BaseIndicator):
	name = "zscore_price"
	category = "price_action"
	description = "Z-Score of Price"

	def calculate(
		self, df: pd.DataFrame, window: int = 20, **kwargs: Any
	) -> IndicatorResult:
		if df.empty or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		rolling_mean = df["close"].rolling(window=window).mean()
		rolling_std = df["close"].rolling(window=window).std()

		zscore = (df["close"] - rolling_mean) / rolling_std
		latest = zscore.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"window": window},
		)


class ZScoreVolumeIndicator(BaseIndicator):
	name = "zscore_volume"
	category = "price_action"
	description = "Z-Score of Volume"

	def calculate(
		self, df: pd.DataFrame, window: int = 20, **kwargs: Any
	) -> IndicatorResult:
		if df.empty or "volume" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		rolling_mean = df["volume"].rolling(window=window).mean()
		rolling_std = df["volume"].rolling(window=window).std()

		zscore = (df["volume"] - rolling_mean) / rolling_std
		latest = zscore.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"window": window},
		)


class DistanceFromMAIndicator(BaseIndicator):
	name = "distance_from_ma"
	category = "price_action"
	description = "Distance from Moving Average (%)"

	def __init__(
		self, name: str = "distance_from_ema20", ma_type: str = "ema", length: int = 20
	):
		self.name = name
		self.ma_type = ma_type
		self.length = length

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		if df.empty or "close" not in df.columns:
			return IndicatorResult(name=self.name, value=None)

		if self.ma_type == "ema":
			ma = pdt.ema(df["close"], length=self.length)
		else:  # sma
			ma = pdt.sma(df["close"], length=self.length)

		distance_pct = (df["close"] - ma) / ma * 100
		latest = distance_pct.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"ma_type": self.ma_type, "length": self.length, "unit": "%"},
		)


class RSIRegimeIndicator(BaseIndicator):
	name = "rsi_regime"
	category = "price_action"
	description = "RSI Market Regime (Overbought/Oversold)"

	def calculate(
		self, df: pd.DataFrame, length: int = 14, **kwargs: Any
	) -> IndicatorResult:
		if df.empty or "close" not in df.columns or len(df) < length + 1:
			return IndicatorResult(name=self.name, value=None)

		rsi = pdt.rsi(df["close"], length=length)
		if rsi is None or rsi.empty:
			return IndicatorResult(name=self.name, value=None)

		latest = rsi.iloc[-1]
		if pd.isna(latest):
			return IndicatorResult(name=self.name, value=None)

		value = float(latest)

		if value >= 70:
			regime, signal = "OVERBOUGHT", "bearish"
		elif value <= 30:
			regime, signal = "OVERSOLD", "bullish"
		elif value >= 60:
			regime, signal = "BULLISH", "bullish"
		elif value <= 40:
			regime, signal = "BEARISH", "bearish"
		else:
			regime, signal = "NEUTRAL", "neutral"

		return IndicatorResult(
			name=self.name,
			value=value,
			signal=signal,
			regime=regime,
			metadata={"rsi_length": length, "rsi_value": value},
		)


registry.register(ReturnsIndicator())
registry.register(LogReturnsIndicator())
registry.register(MomentumIndicator("momentum10", period=10))
registry.register(MomentumIndicator("momentum20", period=20))

registry.register(ZScorePriceIndicator())
registry.register(ZScoreVolumeIndicator())

registry.register(
	DistanceFromMAIndicator("distance_from_ema20", ma_type="ema", length=20)
)
registry.register(
	DistanceFromMAIndicator("distance_from_ema50", ma_type="ema", length=50)
)

registry.register(RSIRegimeIndicator())
