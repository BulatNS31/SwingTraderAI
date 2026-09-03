from typing import Any, Optional

import pandas as pd
import pandas_ta as pdt

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

from .base import BaseIndicator, IndicatorResult
from .registry import registry


class EMAIndicator(BaseIndicator):
	"""Exponential Moving Average по close."""

	category = "trend"
	description = "Exponential Moving Average"

	def __init__(self, name: str = "ema20", length: int = 20) -> None:
		self.name = name
		self.length = length
		self.description = f"Exponential Moving Average ({length})"

	def calculate(
		self, df: pd.DataFrame, length: Optional[int] = None, **kwargs: Any
	) -> IndicatorResult:
		length = length if length is not None else kwargs.get("length", self.length)
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN

		if df.empty or close_col not in df.columns or len(df) < length:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "insufficient_data"},
			)

		ema = pdt.ema(df[close_col], length=length)
		if ema is None or ema.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "calculation_failed"},
			)

		latest = ema.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"length": length},
		)


class WMAIndicator(BaseIndicator):
	"""Weighted Moving Average по close."""

	category = "trend"
	description = "Weighted Moving Average"

	def __init__(self, name: str = "wma20", length: int = 20) -> None:
		self.name = name
		self.length = length
		self.description = f"Weighted Moving Average ({length})"

	def calculate(
		self, df: pd.DataFrame, length: Optional[int] = None, **kwargs: Any
	) -> IndicatorResult:
		length = length if length is not None else kwargs.get("length", self.length)
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN

		if df.empty or close_col not in df.columns or len(df) < length:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "insufficient_data"},
			)

		wma = pdt.wma(df[close_col], length=length)
		if wma is None or wma.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "calculation_failed"},
			)

		latest = wma.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"length": length},
		)


class VWAPIndicator(BaseIndicator):
	"""Cumulative VWAP на всём переданном df.

	Для интрадея предпочтительнее SessionVWAPIndicator (сброс по дням).
	"""

	name = "vwap"
	category = "volume"
	description = "Volume Weighted Average Price (cumulative)"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN
		low_col = MARKET_DATA_SCHEMA.LOW_COLUMN
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN
		volume_col = MARKET_DATA_SCHEMA.VOLUME_COLUMN

		required = [high_col, low_col, close_col, volume_col]
		if df.empty or any(c not in df.columns for c in required):
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "missing_columns"},
			)

		typical_price = (df[high_col] + df[low_col] + df[close_col]) / 3.0
		tpv = typical_price * df[volume_col]
		cum_vol = df[volume_col].cumsum().replace(0, pd.NA)
		vwap_series = tpv.cumsum() / cum_vol

		latest = vwap_series.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"period": "full", "note": "cumulative_from_start"},
		)


class SessionVWAPIndicator(BaseIndicator):
	"""VWAP со сбросом на каждый торговый день (по колонке time)."""

	name = "vwap_session"
	category = "volume"
	description = "Session VWAP (reset by day)"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN
		low_col = MARKET_DATA_SCHEMA.LOW_COLUMN
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN
		volume_col = MARKET_DATA_SCHEMA.VOLUME_COLUMN
		time_col = MARKET_DATA_SCHEMA.TIME_COLUMN

		required = [high_col, low_col, close_col, volume_col, time_col]
		if df.empty or any(c not in df.columns for c in required):
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "missing_columns"},
			)

		work = df.copy()
		work["_session_date"] = pd.to_datetime(work[time_col], utc=True).dt.date

		typical_price = (work[high_col] + work[low_col] + work[close_col]) / 3.0
		tpv = typical_price * work[volume_col]

		cum_tpv = tpv.groupby(work["_session_date"]).cumsum()
		cum_vol = (
			work[volume_col].groupby(work["_session_date"]).cumsum().replace(0, pd.NA)
		)
		vwap_series = cum_tpv / cum_vol

		latest = vwap_series.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"type": "session_vwap"},
		)


# --- Registration (без дублей) ---
registry.register(EMAIndicator("ema9", 9))
registry.register(EMAIndicator("ema20", 20))
registry.register(EMAIndicator("ema50", 50))
registry.register(EMAIndicator("ema200", 200))

registry.register(WMAIndicator("wma10", 10))
registry.register(WMAIndicator("wma20", 20))
registry.register(WMAIndicator("wma50", 50))

registry.register(VWAPIndicator())
registry.register(SessionVWAPIndicator())
