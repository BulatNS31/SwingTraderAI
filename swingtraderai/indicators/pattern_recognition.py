from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

from .base import BaseIndicator, IndicatorResult, calculate_atr
from .registry import registry


def extract_candle_features(df: pd.DataFrame, slope_window: int = 10) -> pd.DataFrame:
	"""
	Извлечение геометрических и микроструктурных признаков свечей.

	- Отношение верхеей/нижней тени к телу свечи
	- Наклон тренда через LinearRegression из scikit-learn
	- Относительный размер тела к ATR
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

	# Нормализованные характеристики свечи
	body_ratio = body_size / candle_range
	upper_shadow_ratio = upper_shadow / candle_range
	lower_shadow_ratio = lower_shadow / candle_range

	# Расчет наклона цены через LinearRegression из scikit-learn
	lr = LinearRegression()
	x = np.arange(slope_window).reshape(-1, 1)

	def calc_slope(window: pd.Series) -> float:
		if len(window) < slope_window or window.isnull().any():
			return 0.0
		y = window.values.reshape(-1, 1)
		lr.fit(x, y)
		return float(lr.coef_[0][0])

	trend_slope = close.rolling(window=slope_window).apply(calc_slope, raw=False)
	atr = calculate_atr(df, window=14)
	relative_body_atr = body_size / atr.replace(0, np.nan)

	return pd.DataFrame(
		{
			"body_ratio": body_ratio.fillna(0),
			"upper_shadow_ratio": upper_shadow_ratio.fillna(0),
			"lower_shadow_ratio": lower_shadow_ratio.fillna(0),
			"trend_slope": trend_slope.fillna(0),
			"relative_body_atr": relative_body_atr.fillna(0),
		},
		index=df.index,
	)


def detect_bulkowski_patterns(
	df: pd.DataFrame, lookback: int = 20, tolerance: float = 0.015
) -> pd.DataFrame:
	"""
	Детекция паттернов Булковски (Double Bottom, Double Top, Hammer, Engulfing).
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df).copy()
	open_p = df[MARKET_DATA_SCHEMA.OPEN_COLUMN]
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]

	features = extract_candle_features(df)

	double_bottom = np.zeros(len(df), dtype=bool)
	double_top = np.zeros(len(df), dtype=bool)
	hammer = np.zeros(len(df), dtype=bool)
	bullish_engulfing = np.zeros(len(df), dtype=bool)

	for i in range(lookback, len(df)):
		window_lows = low.iloc[i - lookback : i]
		window_highs = high.iloc[i - lookback : i]

		curr_low = low.iloc[i]
		curr_high = high.iloc[i]

		# 1. Double Bottom (Двойное Дно)
		min1 = window_lows.min()
		if (
			abs(curr_low - min1) / min1 <= tolerance
			and features["trend_slope"].iloc[i] < 0
		):
			double_bottom[i] = True

		# 2. Double Top (Двойная Вершина)
		max1 = window_highs.max()
		if (
			abs(curr_high - max1) / max1 <= tolerance
			and features["trend_slope"].iloc[i] > 0
		):
			double_top[i] = True

		# 3. Hammer (Молот)
		if (
			features["lower_shadow_ratio"].iloc[i] >= 0.6
			and features["body_ratio"].iloc[i] <= 0.3
			and features["trend_slope"].iloc[i] < 0
		):
			hammer[i] = True

		# 4. Bullish Engulfing (Бычье Поглощение)
		if (
			close.iloc[i - 1] < open_p.iloc[i - 1]
			and close.iloc[i] > open_p.iloc[i]
			and close.iloc[i] >= open_p.iloc[i - 1]
			and open_p.iloc[i] <= close.iloc[i - 1]
		):
			bullish_engulfing[i] = True

	return pd.DataFrame(
		{
			"double_bottom": double_bottom,
			"double_top": double_top,
			"hammer": hammer,
			"bullish_engulfing": bullish_engulfing,
		},
		index=df.index,
	)


class BulkowskiPatternClassifier:
	"""
	Классификатор успешности пробоев паттернов на базе RandomForest.
	Обучается на геометрическом векторе признаков.
	"""

	def __init__(self, n_estimators: int = 50):
		self.model = RandomForestClassifier(n_estimators=n_estimators, random_state=42)
		self.is_fitted = False

	def fit_from_history(
		self,
		features_df: pd.DataFrame,
		pattern_labels: pd.Series,
		target_returns: pd.Series,
	) -> None:
		"""
		Разметка и обучение RandomForest на успешность паттерна.
		Target: True, если доходность после паттерна превысила порог.
		"""
		y = (target_returns > 0.02).astype(
			int
		)  # Пробой считаем успешным при +2% движения
		X = features_df.copy()
		X["pattern_type"] = pattern_labels

		if len(X) > 20:
			self.model.fit(X, y)
			self.is_fitted = True

	def predict_success_probability(self, current_features: pd.DataFrame) -> float:
		if not self.is_fitted:
			# Исторические базовые вероятности Булковски
			# при отсутствии обученной ML-модели
			return 0.65
		proba = self.model.predict_proba(current_features)
		return float(proba[0][1])


class PatternRecognitionIndicator(BaseIndicator):
	name = "pattern_recognition"
	category = "price_action"
	description = (
		"Распознавание паттернов Булковски + ML оценка вероятности на Scikit-Learn"
	)
	default_params = {
		"lookback": 20,
		"tolerance": 0.015,
		"slope_window": 10,
	}

	def __init__(self) -> None:
		super().__init__()
		self.ml_classifier = BulkowskiPatternClassifier()

	def calculate(
		self,
		df: pd.DataFrame,
		lookback: int = 20,
		tolerance: float = 0.015,
		slope_window: int = 10,
		**kwargs: Any,
	) -> IndicatorResult:
		feat_df = extract_candle_features(df, slope_window=slope_window)
		patterns_df = detect_bulkowski_patterns(
			df, lookback=lookback, tolerance=tolerance
		)

		latest_patterns = patterns_df.iloc[-1]
		latest_features = feat_df.iloc[-1:]

		detected_patterns = []
		for pattern_name, is_present in latest_patterns.items():
			if is_present:
				detected_patterns.append(pattern_name)

		# Оценка успешности пробоя
		prob = 0.5
		signal = "neutral"

		if (
			"double_bottom" in detected_patterns
			or "hammer" in detected_patterns
			or "bullish_engulfing" in detected_patterns
		):
			signal = "bullish"
			prob = self.ml_classifier.predict_success_probability(latest_features)
		elif "double_top" in detected_patterns:
			signal = "bearish"
			prob = self.ml_classifier.predict_success_probability(latest_features)

		return IndicatorResult(
			name=self.name,
			value={
				"detected_patterns": detected_patterns,
				"breakout_success_probability": round(prob, 2),
				"trend_slope": float(latest_features["trend_slope"].iloc[0]),
			},
			signal=signal,
			regime="pattern_found" if detected_patterns else "no_pattern",
			metadata={
				"lookback": lookback,
				"tolerance": tolerance,
				"body_ratio": float(latest_features["body_ratio"].iloc[0]),
			},
		)


registry.register(PatternRecognitionIndicator())
