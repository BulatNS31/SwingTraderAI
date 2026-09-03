from typing import Any, Optional

import numpy as np
import pandas as pd

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

from .base import BaseIndicator, IndicatorResult, calculate_atr
from .registry import registry


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
	"""Линейный наклон: (y_t - y_{t-window}) / window."""
	return (series - series.shift(window)) / float(window)


def extract_candle_features(df: pd.DataFrame, slope_window: int = 10) -> pd.DataFrame:
	"""Геометрические признаки свечи.

	- body_ratio / upper_shadow_ratio / lower_shadow_ratio — доли range
	- trend_slope — наклон close за slope_window
	- relative_body_atr — размер тела в ATR
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df).copy()
	open_p = df[MARKET_DATA_SCHEMA.OPEN_COLUMN]
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]

	body_size = (close - open_p).abs()
	candle_range = (high - low).replace(0, np.nan)

	upper_shadow = high - np.maximum(open_p, close)
	lower_shadow = np.minimum(open_p, close) - low

	body_ratio = body_size / candle_range
	upper_shadow_ratio = upper_shadow / candle_range
	lower_shadow_ratio = lower_shadow / candle_range

	trend_slope = _rolling_slope(close, slope_window)
	atr = calculate_atr(df, window=14)
	relative_body_atr = body_size / atr.replace(0, np.nan)

	return pd.DataFrame(
		{
			"body_ratio": body_ratio.fillna(0.0),
			"upper_shadow_ratio": upper_shadow_ratio.fillna(0.0),
			"lower_shadow_ratio": lower_shadow_ratio.fillna(0.0),
			"trend_slope": trend_slope.fillna(0.0),
			"relative_body_atr": relative_body_atr.fillna(0.0),
		},
		index=df.index,
	)


def detect_bulkowski_patterns(
	df: pd.DataFrame,
	lookback: int = 20,
	tolerance: float = 0.015,
	features: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
	"""Детекция паттернов (упрощённый Bulkowski-style).

	Паттерны:
	- double_bottom / double_top — два экстремума в окне на близкой цене
	+ противоположный swing между ними (грубая имитация neckline)
	- hammer / shooting_star — разворотные свечи
	- bullish_engulfing / bearish_engulfing — поглощение тела

	Args:
	df: OHLCV.
	lookback: Окно поиска второго экстремума.
	tolerance: Допуск равенства цен экстремумов (доля от уровня).
	features: Уже посчитанные extract_candle_features (чтобы не считать дважды).
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df).copy()
	open_p = df[MARKET_DATA_SCHEMA.OPEN_COLUMN].to_numpy(dtype=float)
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN].to_numpy(dtype=float)
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN].to_numpy(dtype=float)
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN].to_numpy(dtype=float)

	if features is None:
		features = extract_candle_features(df)

	body_ratio = features["body_ratio"].to_numpy(dtype=float)
	upper_shadow_ratio = features["upper_shadow_ratio"].to_numpy(dtype=float)
	lower_shadow_ratio = features["lower_shadow_ratio"].to_numpy(dtype=float)
	trend_slope = features["trend_slope"].to_numpy(dtype=float)

	n = len(df)
	double_bottom = np.zeros(n, dtype=bool)
	double_top = np.zeros(n, dtype=bool)
	hammer = np.zeros(n, dtype=bool)
	shooting_star = np.zeros(n, dtype=bool)
	bullish_engulfing = np.zeros(n, dtype=bool)
	bearish_engulfing = np.zeros(n, dtype=bool)

	for i in range(lookback, n):
		# ----- Double Bottom -----
		# Ищем в окне [i-lookback, i) минимум, отличный от текущего low,
		# на расстоянии >= lookback//3 баров, с подъёмом между ними.
		curr_low = low[i]
		if curr_low > 0:
			window_low = low[i - lookback : i]
			# индекс минимума внутри окна (относительно начала окна)
			min_idx_rel = int(np.argmin(window_low))
			min_price = float(window_low[min_idx_rel])
			bars_between = lookback - min_idx_rel  # сколько баров от min до i

			if (
				min_price > 0
				and bars_between >= max(3, lookback // 3)
				and abs(curr_low - min_price) / min_price <= tolerance
			):
				# Между минимумами должен быть подъём (neckline-proxy)
				mid_high = float(high[i - lookback + min_idx_rel : i].max())
				if mid_high > min_price * (1.0 + tolerance) and trend_slope[i] <= 0:
					double_bottom[i] = True

		# ----- Double Top -----
		curr_high = high[i]
		if curr_high > 0:
			window_high = high[i - lookback : i]
			max_idx_rel = int(np.argmax(window_high))
			max_price = float(window_high[max_idx_rel])
			bars_between = lookback - max_idx_rel

			if (
				max_price > 0
				and bars_between >= max(3, lookback // 3)
				and abs(curr_high - max_price) / max_price <= tolerance
			):
				mid_low = float(low[i - lookback + max_idx_rel : i].min())
				if mid_low < max_price * (1.0 - tolerance) and trend_slope[i] >= 0:
					double_top[i] = True

		# ----- Hammer (разворот вверх после снижения) -----
		# Нижняя тень >= 60% range, тело <= 30%, close в верхней половине,
		# предшествующий наклон вниз.
		rng = high[i] - low[i]
		if rng > 0:
			close_pos = (close[i] - low[i]) / rng  # 0 = low, 1 = high
			if (
				lower_shadow_ratio[i] >= 0.6
				and body_ratio[i] <= 0.3
				and close_pos >= 0.5
				and trend_slope[i] < 0
			):
				hammer[i] = True

			# ----- Shooting Star (разворот вниз после роста) -----
			if (
				upper_shadow_ratio[i] >= 0.6
				and body_ratio[i] <= 0.3
				and close_pos <= 0.5
				and trend_slope[i] > 0
			):
				shooting_star[i] = True

		# ----- Bullish Engulfing -----
		# prev медвежья, curr бычья, тело curr поглощает тело prev
		if i >= 1:
			prev_bear = close[i - 1] < open_p[i - 1]
			curr_bull = close[i] > open_p[i]
			engulfs = close[i] >= open_p[i - 1] and open_p[i] <= close[i - 1]
			if prev_bear and curr_bull and engulfs:
				bullish_engulfing[i] = True

			# ----- Bearish Engulfing -----
			prev_bull = close[i - 1] > open_p[i - 1]
			curr_bear = close[i] < open_p[i]
			engulfs_bear = open_p[i] >= close[i - 1] and close[i] <= open_p[i - 1]
			if prev_bull and curr_bear and engulfs_bear:
				bearish_engulfing[i] = True

	return pd.DataFrame(
		{
			"double_bottom": double_bottom,
			"double_top": double_top,
			"hammer": hammer,
			"shooting_star": shooting_star,
			"bullish_engulfing": bullish_engulfing,
			"bearish_engulfing": bearish_engulfing,
		},
		index=df.index,
	)


class PatternRecognitionIndicator(BaseIndicator):
	"""Распознавание свечных/разворотных паттернов (Bulkowski-style).

	ML-скор успешности вынесен из hot-path: здесь только детерминированные флаги.
	Для setup-level вероятности используйте ml/setups + setup_inference.
	"""

	name = "pattern_recognition"
	category = "price_action"
	description = "Паттерны: double bottom/top, hammer, shooting star, engulfing"
	default_params = {
		"lookback": 20,
		"tolerance": 0.015,
		"slope_window": 10,
	}

	def calculate(
		self,
		df: pd.DataFrame,
		lookback: int = 20,
		tolerance: float = 0.015,
		slope_window: int = 10,
		**kwargs: Any,
	) -> IndicatorResult:
		if df is None or df.empty:
			return IndicatorResult(
				name=self.name,
				value={"detected_patterns": []},
				signal="neutral",
				regime="no_pattern",
				metadata={"error": "empty_dataframe"},
			)

		feat_df = extract_candle_features(df, slope_window=slope_window)
		patterns_df = detect_bulkowski_patterns(
			df,
			lookback=lookback,
			tolerance=tolerance,
			features=feat_df,
		)

		latest_patterns = patterns_df.iloc[-1]
		latest_features = feat_df.iloc[-1]

		detected = [name for name, present in latest_patterns.items() if bool(present)]

		bullish = {"double_bottom", "hammer", "bullish_engulfing"}
		bearish = {"double_top", "shooting_star", "bearish_engulfing"}

		has_bull = bool(bullish.intersection(detected))
		has_bear = bool(bearish.intersection(detected))

		if has_bull and not has_bear:
			signal = "bullish"
		elif has_bear and not has_bull:
			signal = "bearish"
		elif has_bull and has_bear:
			signal = "mixed"
		else:
			signal = "neutral"

		return IndicatorResult(
			name=self.name,
			value={
				"detected_patterns": detected,
				"trend_slope": float(latest_features["trend_slope"]),
				"body_ratio": float(latest_features["body_ratio"]),
				"upper_shadow_ratio": float(latest_features["upper_shadow_ratio"]),
				"lower_shadow_ratio": float(latest_features["lower_shadow_ratio"]),
			},
			signal=signal,
			regime="pattern_found" if detected else "no_pattern",
			metadata={
				"lookback": lookback,
				"tolerance": tolerance,
				"slope_window": slope_window,
			},
		)


registry.register(PatternRecognitionIndicator())
