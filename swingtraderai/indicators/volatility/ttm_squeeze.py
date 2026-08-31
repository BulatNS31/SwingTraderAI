from typing import Any

import numpy as np
import pandas as pd

from swingtraderai.indicators.base import BaseIndicator, IndicatorResult, calculate_atr
from swingtraderai.indicators.registry import registry
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


def calculate_ttm_squeeze(
	df: pd.DataFrame,
	bb_length: int = 20,
	bb_mult: float = 2.0,
	kc_length: int = 20,
	kc_mult: float = 1.5,
	mom_length: int = 20,
) -> pd.DataFrame:
	"""
	Расчет индикатора TTM Squeeze (John Carter).

	- Squeeze Status: True, если Bollinger Bands входят внутрь Keltner Channels.
	- Momentum Value: Значение моментума на основе линейной регрессии.
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df).copy()
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]

	# --- 1. Bollinger Bands ---
	bb_sma = close.rolling(window=bb_length).mean()
	bb_std = close.rolling(window=bb_length).std(ddof=0)
	bb_upper = bb_sma + (bb_mult * bb_std)
	bb_lower = bb_sma - (bb_mult * bb_std)

	# --- 2. Keltner Channels ---
	kc_sma = close.rolling(window=kc_length).mean()
	atr = calculate_atr(df, window=kc_length)
	kc_upper = kc_sma + (kc_mult * atr)
	kc_lower = kc_sma - (kc_mult * atr)

	# --- 3. Squeeze Detection ---
	# Squeeze ON: полосы Боллинджера СТРОГО внутри каналов Кельтнера
	squeeze_on = (bb_upper < kc_upper) & (bb_lower > kc_lower)

	# --- 4. Momentum Oscillator (LinReg Delta) ---
	# Средняя точка Donchian + SMA
	donchian_mid = (
		high.rolling(window=mom_length).max() + low.rolling(window=mom_length).min()
	) / 2
	delta_base = (donchian_mid + kc_sma) / 2
	delta = close - delta_base

	# Линейная регрессия методом наименьших квадратов по скользящему окну
	x = np.arange(mom_length)
	x_mean = x.mean()
	x_var = ((x - x_mean) ** 2).sum()

	def linreg_last(series_window: pd.Series) -> float:
		if len(series_window) < mom_length or series_window.isnull().any():
			return float(np.nan)
		y = series_window.values
		y_mean = y.mean()
		slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
		intercept = y_mean - slope * x_mean
		result: float = float(slope * (mom_length - 1) + intercept)
		return result

	momentum = delta.rolling(window=mom_length).apply(linreg_last, raw=False)

	return pd.DataFrame(
		{
			"squeeze_on": squeeze_on,
			"momentum": momentum,
			"bb_upper": bb_upper,
			"bb_lower": bb_lower,
			"kc_upper": kc_upper,
			"kc_lower": kc_lower,
		},
		index=df.index,
	)


class TTMSqueezeIndicator(BaseIndicator):
	name = "ttm_squeeze"
	category = "volatility"
	description = (
		"TTM Squeeze (John Carter) - Сжатие волатильности BB в KC с моментумом"
	)
	default_params = {
		"bb_length": 20,
		"bb_mult": 2.0,
		"kc_length": 20,
		"kc_mult": 1.5,
		"mom_length": 20,
	}

	def calculate(
		self,
		df: pd.DataFrame,
		bb_length: int = 20,
		bb_mult: float = 2.0,
		kc_length: int = 20,
		kc_mult: float = 1.5,
		mom_length: int = 20,
		**kwargs: Any,
	) -> IndicatorResult:
		squeeze_df = calculate_ttm_squeeze(
			df,
			bb_length=bb_length,
			bb_mult=bb_mult,
			kc_length=kc_length,
			kc_mult=kc_mult,
			mom_length=mom_length,
		)

		latest = squeeze_df.iloc[-1]
		prev = squeeze_df.iloc[-2] if len(squeeze_df) > 1 else latest

		is_squeeze = bool(latest["squeeze_on"])
		was_squeeze = bool(prev["squeeze_on"])
		curr_mom = float(latest["momentum"]) if pd.notna(latest["momentum"]) else 0.0
		prev_mom = float(prev["momentum"]) if pd.notna(prev["momentum"]) else 0.0

		# Формирование сигнала
		signal = "neutral"
		regime = "squeeze" if is_squeeze else "firing"

		if was_squeeze and not is_squeeze:
			# Сжатие разжалось (Squeeze Fired)
			if curr_mom > 0:
				signal = "bullish"
			elif curr_mom < 0:
				signal = "bearish"
		elif not is_squeeze:
			if curr_mom > 0 and curr_mom > prev_mom:
				signal = "bullish"
			elif curr_mom < 0 and curr_mom < prev_mom:
				signal = "bearish"

		return IndicatorResult(
			name=self.name,
			value={
				"squeeze_on": is_squeeze,
				"momentum": curr_mom,
				"momentum_increasing": curr_mom > prev_mom,
			},
			signal=signal,
			regime=regime,
			metadata={
				"bb_length": bb_length,
				"kc_length": kc_length,
				"squeeze_fired": was_squeeze and not is_squeeze,
			},
		)


registry.register(TTMSqueezeIndicator())
