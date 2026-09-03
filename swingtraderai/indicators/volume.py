from typing import Any, Optional

import pandas as pd
import pandas_ta as pdt

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

from .base import BaseIndicator, IndicatorResult
from .registry import registry


def _first_col(df: pd.DataFrame, prefix: str) -> Optional[str]:
	"""Имя первой колонки с данным префиксом (устойчиво к версиям pandas_ta)."""
	for c in df.columns:
		if str(c).startswith(prefix):
			return str(c)
	return None


class BollingerBandsIndicator(BaseIndicator):
	"""Bollinger Bands: upper / middle / lower / bandwidth."""

	name = "bbands"
	category = "volatility"
	description = "Bollinger Bands"

	def __init__(
		self,
		name: str = "bbands",
		length: int = 20,
		std: float = 2.0,
	) -> None:
		self.name = name
		self.length = length
		self.std = std
		self.description = f"Bollinger Bands ({length}, {std})"

	def calculate(
		self,
		df: pd.DataFrame,
		length: Optional[int] = None,
		std: Optional[float] = None,
		**kwargs: Any,
	) -> IndicatorResult:
		length = length if length is not None else kwargs.get("length", self.length)
		std = std if std is not None else kwargs.get("std", self.std)
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN

		if df.empty or close_col not in df.columns or len(df) < length:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={
					"error": "insufficient_data",
					"required_rows": length,
					"available_rows": len(df),
				},
			)

		bb = pdt.bbands(close=df[close_col], length=length, std=std)
		if bb is None or bb.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "calculation_failed"},
			)

		latest = bb.iloc[-1]
		upper_c = _first_col(bb, "BBU_")
		mid_c = _first_col(bb, "BBM_")
		lower_c = _first_col(bb, "BBL_")
		bw_c = _first_col(bb, "BBB_")

		def _val(col: Optional[str]) -> Optional[float]:
			if col is None:
				return None
			v = latest.get(col)
			return float(v) if pd.notna(v) else None

		return IndicatorResult(
			name=self.name,
			value={
				"upper": _val(upper_c),
				"middle": _val(mid_c),
				"lower": _val(lower_c),
				"bandwidth": _val(bw_c),
			},
			metadata={"length": length, "std": std},
		)


class ATRIndicator(BaseIndicator):
	"""Average True Range."""

	name = "atr"
	category = "volatility"
	description = "Average True Range"

	def __init__(self, name: str = "atr", length: int = 14) -> None:
		self.name = name
		self.length = length
		self.description = f"Average True Range ({length})"

	def calculate(
		self, df: pd.DataFrame, length: Optional[int] = None, **kwargs: Any
	) -> IndicatorResult:
		length = length if length is not None else kwargs.get("length", self.length)
		high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN
		low_col = MARKET_DATA_SCHEMA.LOW_COLUMN
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN

		required = [high_col, low_col, close_col]
		if df.empty or any(c not in df.columns for c in required) or len(df) < length:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "insufficient_data"},
			)

		atr = pdt.atr(df[high_col], df[low_col], df[close_col], length=length)
		if atr is None or atr.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "calculation_failed"},
			)

		latest = atr.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"length": length},
		)


class DonchianChannelsIndicator(BaseIndicator):
	"""Donchian Channels: upper / lower / middle."""

	name = "donchian"
	category = "volatility"
	description = "Donchian Channels"

	def __init__(self, name: str = "donchian", length: int = 20) -> None:
		self.name = name
		self.length = length
		self.description = f"Donchian Channels ({length})"

	def calculate(
		self, df: pd.DataFrame, length: Optional[int] = None, **kwargs: Any
	) -> IndicatorResult:
		length = length if length is not None else kwargs.get("length", self.length)
		high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN
		low_col = MARKET_DATA_SCHEMA.LOW_COLUMN

		if (
			df.empty
			or high_col not in df.columns
			or low_col not in df.columns
			or len(df) < length
		):
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "insufficient_data"},
			)

		dc = pdt.donchian(
			df[high_col],
			df[low_col],
			lower_length=length,
			upper_length=length,
		)
		if dc is None or dc.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "calculation_failed"},
			)

		latest = dc.iloc[-1]
		upper_c = _first_col(dc, "DCU_")
		lower_c = _first_col(dc, "DCL_")
		mid_c = _first_col(dc, "DCM_")

		def _val(col: Optional[str]) -> Optional[float]:
			if col is None:
				return None
			v = latest.get(col)
			return float(v) if pd.notna(v) else None

		return IndicatorResult(
			name=self.name,
			value={
				"upper": _val(upper_c),
				"lower": _val(lower_c),
				"middle": _val(mid_c),
			},
			metadata={"length": length},
		)


class VolumeSMAIndicator(BaseIndicator):
	"""SMA по объёму."""

	category = "volume"
	description = "Volume Simple Moving Average"

	def __init__(self, name: str = "volume_sma", length: int = 20) -> None:
		self.name = name
		self.length = length
		self.description = f"Volume Simple Moving Average ({length})"

	def calculate(
		self, df: pd.DataFrame, length: Optional[int] = None, **kwargs: Any
	) -> IndicatorResult:
		length = length if length is not None else kwargs.get("length", self.length)
		volume_col = MARKET_DATA_SCHEMA.VOLUME_COLUMN

		if df.empty or volume_col not in df.columns or len(df) < length:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "insufficient_data"},
			)

		sma = pdt.sma(df[volume_col], length=length)
		if sma is None or sma.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"length": length, "error": "calculation_failed"},
			)

		latest = sma.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
			metadata={"length": length},
		)


class OBVIndicator(BaseIndicator):
	"""On-Balance Volume."""

	name = "obv"
	category = "volume"
	description = "On-Balance Volume"

	def calculate(self, df: pd.DataFrame, **kwargs: Any) -> IndicatorResult:
		close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN
		volume_col = MARKET_DATA_SCHEMA.VOLUME_COLUMN

		if df.empty or close_col not in df.columns or volume_col not in df.columns:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "missing_columns"},
			)

		obv = pdt.obv(df[close_col], df[volume_col])
		if obv is None or obv.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "calculation_failed"},
			)

		latest = obv.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
		)


class ADIndicator(BaseIndicator):
	"""Accumulation / Distribution Line."""

	name = "ad"
	category = "volume"
	description = "Accumulation / Distribution Line"

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

		ad = pdt.ad(df[high_col], df[low_col], df[close_col], df[volume_col])
		if ad is None or ad.empty:
			return IndicatorResult(
				name=self.name,
				value=None,
				metadata={"error": "calculation_failed"},
			)

		latest = ad.iloc[-1]
		return IndicatorResult(
			name=self.name,
			value=float(latest) if pd.notna(latest) else None,
		)


registry.register(BollingerBandsIndicator())
registry.register(ATRIndicator())
registry.register(ATRIndicator(name="atr10", length=10))
registry.register(ATRIndicator(name="atr20", length=20))

registry.register(DonchianChannelsIndicator())

registry.register(VolumeSMAIndicator(name="volume_sma10", length=10))
registry.register(VolumeSMAIndicator(name="volume_sma20", length=20))

registry.register(OBVIndicator())
registry.register(ADIndicator())
