from typing import Any, Tuple

import numpy as np
import pandas as pd

from swingtraderai.indicators.base import BaseIndicator, IndicatorResult
from swingtraderai.indicators.registry import registry
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


def calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
	"""Стандартный расчет RSI."""
	delta = series.diff()
	gain = delta.clip(lower=0)
	loss = -delta.clip(upper=0)

	avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
	avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()

	rs = avg_gain / avg_loss.replace(0, np.nan)
	return 100 - (100 / (1 + rs))


def calculate_macd(
	series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
	"""Расчет MACD (Line, Signal, Histogram)."""
	ema_fast = series.ewm(span=fast, adjust=False).mean()
	ema_slow = series.ewm(span=slow, adjust=False).mean()
	macd_line = ema_fast - ema_slow
	signal_line = macd_line.ewm(span=signal, adjust=False).mean()
	macd_hist = macd_line - signal_line
	return macd_line, signal_line, macd_hist


def find_confirmed_pivots(
	series: pd.Series, left: int = 2, right: int = 2
) -> Tuple[pd.Series, pd.Series]:
	"""
	Находит подтвержденные локальные экстремумы (Pivot High / Pivot Low).
	ВАЖНО: Результат сдвигается на `right` свечей назад для исключения Lookahead Bias!
	"""
	# Маска локального максимума в окне (left + 1 + right)
	window = left + 1 + right
	is_pivot_high = series == series.rolling(window=window, min_periods=window).max()
	is_pivot_low = series == series.rolling(window=window, min_periods=window).min()

	# Сдвигаем назад, так как пик подтверждается только через `right` баров
	pivot_highs = series.where(is_pivot_high).shift(right)
	pivot_lows = series.where(is_pivot_low).shift(right)

	return pivot_highs, pivot_lows


def detect_divergences(
	df: pd.DataFrame,
	oscillator_type: str = "rsi",
	pivot_window: int = 3,
	max_lookback: int = 30,
	rsi_period: int = 14,
	macd_fast: int = 12,
	macd_slow: int = 26,
	macd_signal: int = 9,
) -> pd.DataFrame:
	"""
	Детектор бычьих и медвежьих дивергенций по Найману.

	Бычья дивергенция (Bullish):
	- Цена делает новый минимум (Low_2 < Low_1)
	- Осциллятор делает более высокий минимум (Osc_2 > Osc_1)

	Медвежья дивергенция (Bearish):
	- Цена делает новый максимум (High_2 > High_1)
	- Осциллятор делает более низкий максимум (Osc_2 < Osc_1)
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df).copy()
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	# low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]

	# --- 1. Расчет Осциллятора ---
	if oscillator_type.lower() == "rsi":
		osc = calculate_rsi(close, window=rsi_period)
	elif oscillator_type.lower() == "macd":
		_, _, osc = calculate_macd(
			close, fast=macd_fast, slow=macd_slow, signal=macd_signal
		)
	else:
		raise ValueError("oscillator_type должен быть 'rsi' или 'macd'")

	# --- 2. Поиск пиков и впадин без Lookahead Bias ---
	price_p_highs, price_p_lows = find_confirmed_pivots(
		high, left=pivot_window, right=pivot_window
	)
	osc_p_highs, osc_p_lows = find_confirmed_pivots(
		osc, left=pivot_window, right=pivot_window
	)

	bullish_div = np.zeros(len(df), dtype=bool)
	bearish_div = np.zeros(len(df), dtype=bool)

	# --- 3. Поиск дивергенций по локальным экстремумам ---
	for i in range(max_lookback, len(df)):
		# Поиск медвежьей дивергенции на максимумах
		if pd.notna(price_p_highs.iloc[i]):
			curr_price_high = price_p_highs.iloc[i]
			curr_osc_high = osc.iloc[i - pivot_window]

			# Ищем предыдущий подтвержденный пик в окне lookback
			prev_window_price = price_p_highs.iloc[i - max_lookback : i - 1].dropna()
			if not prev_window_price.empty:
				prev_idx = prev_window_price.index[-1]
				prev_price_high = price_p_highs.loc[prev_idx]
				prev_osc_high = osc.loc[prev_idx - pivot_window]

				# Условие медвежьей дивергенции:
				# высший пик цены + низший пик осциллятора
				if curr_price_high > prev_price_high and curr_osc_high < prev_osc_high:
					bearish_div[i] = True

		# Поиск бычьей дивергенции на минимумах
		if pd.notna(price_p_lows.iloc[i]):
			curr_price_low = price_p_lows.iloc[i]
			curr_osc_low = osc.iloc[i - pivot_window]

			# Ищем предыдущий подтвержденный минимум в окне lookback
			prev_window_low = price_p_lows.iloc[i - max_lookback : i - 1].dropna()
			if not prev_window_low.empty:
				prev_idx = prev_window_low.index[-1]
				prev_price_low = price_p_lows.loc[prev_idx]
				prev_osc_low = osc.loc[prev_idx - pivot_window]

				# Условие бычьей дивергенции:
				# низший минимум цены + высший минимум осциллятора
				if curr_price_low < prev_price_low and curr_osc_low > prev_osc_low:
					bullish_div[i] = True

	return pd.DataFrame(
		{
			"bullish_divergence": bullish_div,
			"bearish_divergence": bearish_div,
			"oscillator_value": osc,
		},
		index=df.index,
	)


class DivergenceIndicator(BaseIndicator):
	name = "divergence"
	category = "momentum"
	description = "Дивергенции Эрика Наймана (Бычьи/Медвежьи) на RSI или MACD"
	default_params = {
		"oscillator_type": "rsi",
		"pivot_window": 3,
		"max_lookback": 30,
		"rsi_period": 14,
	}

	def calculate(
		self,
		df: pd.DataFrame,
		oscillator_type: str = "rsi",
		pivot_window: int = 3,
		max_lookback: int = 30,
		rsi_period: int = 14,
		macd_fast: int = 12,
		macd_slow: int = 26,
		macd_signal: int = 9,
		**kwargs: Any,
	) -> IndicatorResult:
		div_df = detect_divergences(
			df,
			oscillator_type=oscillator_type,
			pivot_window=pivot_window,
			max_lookback=max_lookback,
			rsi_period=rsi_period,
			macd_fast=macd_fast,
			macd_slow=macd_slow,
			macd_signal=macd_signal,
		)

		latest = div_df.iloc[-1]

		is_bullish = bool(latest["bullish_divergence"])
		is_bearish = bool(latest["bearish_divergence"])

		signal = "neutral"
		if is_bullish:
			signal = "bullish"
		elif is_bearish:
			signal = "bearish"

		return IndicatorResult(
			name=self.name,
			value={
				"bullish_divergence": is_bullish,
				"bearish_divergence": is_bearish,
				"oscillator_value": (
					float(latest["oscillator_value"])
					if pd.notna(latest["oscillator_value"])
					else None
				),
			},
			signal=signal,
			regime="divergence_detected" if (is_bullish or is_bearish) else "normal",
			metadata={
				"oscillator_type": oscillator_type,
				"pivot_window": pivot_window,
				"max_lookback": max_lookback,
			},
		)


registry.register(DivergenceIndicator())
