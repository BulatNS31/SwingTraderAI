from typing import Any, Tuple

import numpy as np
import pandas as pd

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

from .base import BaseIndicator, IndicatorResult
from .registry import registry


def detect_fractal_highs_lows(
	df: pd.DataFrame, window: int = 2
) -> Tuple[pd.Series, pd.Series]:
	"""Fractal High/Low (Bill Williams).

	Фрактал — локальный экстремум: high/low строго максимален/минимален
	среди window баров слева и window баров справа.

	Args:
	df: OHLCV DataFrame.
	window: Число баров с каждой стороны (2 → окно из 5 баров).

	Returns:
	(fractal_high, fractal_low) — Series с ценой фрактала или NaN.
	На последних window барах почти всегда NaN (нет правого контекста).
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]

	# center=True: текущий бар сравнивается с соседями слева и справа
	roll_max = high.rolling(window * 2 + 1, center=True, min_periods=window + 1).max()
	roll_min = low.rolling(window * 2 + 1, center=True, min_periods=window + 1).min()

	is_fractal_high = high == roll_max
	is_fractal_low = low == roll_min

	return high.where(is_fractal_high), low.where(is_fractal_low)


def rolling_support_resistance_zones(
	df: pd.DataFrame,
	window: int = 100,
	min_touches: int = 3,
	price_tolerance: float = 0.003,
) -> pd.DataFrame:
	"""Горизонтальные S/R по частоте касаний в скользящем окне.

	Цены кластеризуются в бины шириной ~price_tolerance от медианы.
	Уровень = бин с наибольшим числом касаний (>= min_touches).

	Args:
	df: OHLCV.
	window: Размер окна в барах.
	min_touches: Минимум касаний, чтобы уровень считался значимым.
	price_tolerance: Относительная ширина бина (0.003 = 0.3%).

	Returns:
	DataFrame: support_level, resistance_level,
	touches_support, touches_resistance.
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	n = len(df)

	support_level = np.full(n, np.nan)
	resistance_level = np.full(n, np.nan)
	touches_support = np.zeros(n, dtype=int)
	touches_resistance = np.zeros(n, dtype=int)

	low_col = MARKET_DATA_SCHEMA.LOW_COLUMN
	high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN

	for i in range(window, n):
		window_df = df.iloc[i - window : i]

		# --- Support (кластер lows) ---
		lows = window_df[low_col].to_numpy()
		if len(lows) >= min_touches:
			ref = float(np.median(lows))
			if ref > 0:
				bin_size = ref * price_tolerance
				rounded = np.round(lows / bin_size) * bin_size
				unique, counts = np.unique(rounded, return_counts=True)
				mask = counts >= min_touches
				if mask.any():
					idx = np.argmax(counts[mask])
					support_level[i] = unique[mask][idx]
					touches_support[i] = int(counts[mask][idx])

		# --- Resistance (кластер highs) ---
		highs = window_df[high_col].to_numpy()
		if len(highs) >= min_touches:
			ref = float(np.median(highs))
			if ref > 0:
				bin_size = ref * price_tolerance
				rounded = np.round(highs / bin_size) * bin_size
				unique, counts = np.unique(rounded, return_counts=True)
				mask = counts >= min_touches
				if mask.any():
					idx = np.argmax(counts[mask])
					resistance_level[i] = unique[mask][idx]
					touches_resistance[i] = int(counts[mask][idx])

	return pd.DataFrame(
		{
			"support_level": support_level,
			"resistance_level": resistance_level,
			"touches_support": touches_support,
			"touches_resistance": touches_resistance,
		},
		index=df.index,  # сохраняем исходный индекс
	)


def calculate_classic_pivot_points(
	df: pd.DataFrame, timeframe: str = "D"
) -> pd.DataFrame:
	"""Классические Pivot Points с выравниванием по времени

	Считаются на ресемпле (D/W), затем forward-fill на исходные бары.
	Формулы: PP=(H+L+C)/3, R1=2*PP-L, S1=2*PP-H, R2=PP+(H-L), S2=PP-(H-L).
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	temp = df.copy()

	if "time" in temp.columns:
		temp = temp.set_index("time")

	if not isinstance(temp.index, pd.DatetimeIndex):
		raise ValueError("Для pivot points нужен DatetimeIndex или колонка 'time'")

	high, low, close = (
		MARKET_DATA_SCHEMA.HIGH_COLUMN,
		MARKET_DATA_SCHEMA.LOW_COLUMN,
		MARKET_DATA_SCHEMA.CLOSE_COLUMN,
	)

	daily = temp.resample(timeframe).agg({high: "max", low: "min", close: "last"})
	pp = (daily[high] + daily[low] + daily[close]) / 3

	pivot_df = pd.DataFrame(
		{
			"pp": pp,
			"r1": 2 * pp - daily[low],
			"s1": 2 * pp - daily[high],
			"r2": pp + (daily[high] - daily[low]),
			"s2": pp - (daily[high] - daily[low]),
		},
		index=daily.index,
	)

	# Растягиваем на исходный таймфрейм
	result = pivot_df.reindex(temp.index, method="ffill")
	result = result.reset_index(drop=True)
	return result


def add_key_levels_indicators(
	df: pd.DataFrame, fractal_window: int = 2, sr_window: int = 100, pivot_tf: str = "D"
) -> pd.DataFrame:
	"""Добавляет fractal / S-R / pivot колонки в df (feature engineering)."""
	df = df.copy()

	# Fractals
	f_high, f_low = detect_fractal_highs_lows(df, window=fractal_window)
	df["fractal_high"] = f_high
	df["fractal_low"] = f_low

	# Support / Resistance
	zones = rolling_support_resistance_zones(df, window=sr_window)
	df = pd.concat([df, zones], axis=1)

	# Pivot Points
	try:
		pivots = calculate_classic_pivot_points(df, timeframe=pivot_tf)
		df = pd.concat([df, pivots], axis=1)
	except ValueError:
		# нет datetime-индекса — пивоты пропускаем
		pass

	return df


class FractalIndicator(BaseIndicator):
	name = "fractal"
	category = "levels"
	description = "Bill Williams Fractals (локальные экстремумы)"

	def calculate(
		self, df: pd.DataFrame, window: int = 2, **kwargs: Any
	) -> IndicatorResult:
		f_high, f_low = detect_fractal_highs_lows(df, window=window)
		# Берём последний *подтверждённый* фрактал, не iloc[-1] (там часто NaN)
		last_high = f_high.dropna().iloc[-1] if f_high.notna().any() else None
		last_low = f_low.dropna().iloc[-1] if f_low.notna().any() else None

		return IndicatorResult(
			name=self.name,
			value={
				"fractal_high": float(last_high) if last_high is not None else None,
				"fractal_low": float(last_low) if last_low is not None else None,
			},
			metadata={"window": window},
		)


class SupportResistanceIndicator(BaseIndicator):
	name = "sr_levels"
	category = "levels"
	description = "Динамические уровни поддержки и сопротивления по касаниям"

	def calculate(
		self, df: pd.DataFrame, window: int = 120, **kwargs: Any
	) -> IndicatorResult:
		zones = rolling_support_resistance_zones(
			df, window=window, min_touches=3, price_tolerance=0.003
		)
		latest = zones.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value={
				"support": (
					float(latest["support_level"])
					if pd.notna(latest["support_level"])
					else None
				),
				"resistance": (
					float(latest["resistance_level"])
					if pd.notna(latest["resistance_level"])
					else None
				),
				"touches_support": int(latest["touches_support"]),
				"touches_resistance": int(latest["touches_resistance"]),
			},
			metadata={"window": window},
		)


class PivotPointsIndicator(BaseIndicator):
	name = "pivot_points"
	category = "levels"
	description = "Classic Pivot Points (Daily/Weekly)"

	def calculate(
		self, df: pd.DataFrame, timeframe: str = "D", **kwargs: Any
	) -> IndicatorResult:
		pivots = calculate_classic_pivot_points(df, timeframe=timeframe)
		latest = pivots.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value={
				"pp": float(latest["pp"]) if pd.notna(latest["pp"]) else None,
				"r1": float(latest["r1"]) if pd.notna(latest["r1"]) else None,
				"s1": float(latest["s1"]) if pd.notna(latest["s1"]) else None,
				"r2": float(latest["r2"]) if pd.notna(latest["r2"]) else None,
				"s2": float(latest["s2"]) if pd.notna(latest["s2"]) else None,
			},
			metadata={"timeframe": timeframe},
		)


registry.register(FractalIndicator())
registry.register(SupportResistanceIndicator())
registry.register(PivotPointsIndicator())
