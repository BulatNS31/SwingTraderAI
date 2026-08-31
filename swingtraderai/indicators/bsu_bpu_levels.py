from typing import Any

import numpy as np
import pandas as pd

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

from .base import BaseIndicator, IndicatorResult, calculate_atr
from .registry import registry


def detect_bsu_bpu_levels(
	df: pd.DataFrame,
	lookback: int = 60,
	atr_window: int = 14,
	level_tolerance_atr_mult: float = 0.05,
	min_bpu_count: int = 2,
) -> pd.DataFrame:
	"""
	Детектор уровней по методологии А. Герчика (БСУ -> БПУ1 -> БПУ2).

	БСУ (Базовый свечной уровень) — экстремум в локальном окне.
	БПУ (Бары, подтверждающие уровень) — следующие бары, хаи/лои которых
	касаются цены БСУ без существенного пробоя.
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df).copy()
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]
	# close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	# open_p = df[MARKET_DATA_SCHEMA.OPEN_COLUMN]

	atr = calculate_atr(df, window=atr_window)
	df["atr"] = atr

	# bsu_resistance = np.nan
	# bsu_support = np.nan

	res_bpu_count = np.zeros(len(df), dtype=int)
	sup_bpu_count = np.zeros(len(df), dtype=int)

	detected_res_levels = np.full(len(df), np.nan)
	detected_sup_levels = np.full(len(df), np.nan)
	res_atr_left = np.full(len(df), np.nan)
	sup_atr_left = np.full(len(df), np.nan)

	for i in range(lookback, len(df)):
		curr_atr = atr.iloc[i]
		if np.isnan(curr_atr) or curr_atr == 0:
			continue

		tolerance = curr_atr * level_tolerance_atr_mult

		# --- Сопротивление (BSU High) ---
		window_highs = high.iloc[i - lookback : i]
		potential_bsu_res = window_highs.max()

		# Проверяем подтверждение уровня через БПУ
		# (насколько близко High баров подходят к БСУ)
		res_touches = (
			high.iloc[i - lookback : i] - potential_bsu_res
		).abs() <= tolerance
		bpu_res_cnt = res_touches.sum()

		if bpu_res_cnt >= min_bpu_count:
			detected_res_levels[i] = potential_bsu_res
			res_bpu_count[i] = bpu_res_cnt
			# Запас хода = (Уровень - Low текущего барам) / ATR
			res_atr_left[i] = (potential_bsu_res - low.iloc[i]) / curr_atr

		# --- Поддержка (BSU Low) ---
		window_lows = low.iloc[i - lookback : i]
		potential_bsu_sup = window_lows.min()

		sup_touches = (
			low.iloc[i - lookback : i] - potential_bsu_sup
		).abs() <= tolerance
		bpu_sup_cnt = sup_touches.sum()

		if bpu_sup_cnt >= min_bpu_count:
			detected_sup_levels[i] = potential_bsu_sup
			sup_bpu_count[i] = bpu_sup_cnt
			# Запас хода = (High текущего бара - Уровень) / ATR
			sup_atr_left[i] = (high.iloc[i] - potential_bsu_sup) / curr_atr

	result = pd.DataFrame(
		{
			"bsu_bpu_res_level": detected_res_levels,
			"bsu_bpu_sup_level": detected_sup_levels,
			"res_bpu_count": res_bpu_count,
			"sup_bpu_count": sup_bpu_count,
			"res_atr_left": res_atr_left,
			"sup_atr_left": sup_atr_left,
		},
		index=df.index,
	)

	return result


class BsuBpuLevelIndicator(BaseIndicator):
	name = "bsu_bpu_levels"
	category = "levels"
	description = "Уровни Герчика (БСУ/БПУ), накопление и расчет Запаса Хода в ATR"

	def calculate(
		self,
		df: pd.DataFrame,
		lookback: int = 60,
		atr_window: int = 14,
		tolerance_mult: float = 0.05,
		**kwargs: Any,
	) -> IndicatorResult:
		res_df = detect_bsu_bpu_levels(
			df,
			lookback=lookback,
			atr_window=atr_window,
			level_tolerance_atr_mult=tolerance_mult,
		)

		latest = res_df.iloc[-1]

		return IndicatorResult(
			name=self.name,
			value={
				"resistance_level": (
					float(latest["bsu_bpu_res_level"])
					if pd.notna(latest["bsu_bpu_res_level"])
					else None
				),
				"support_level": (
					float(latest["bsu_bpu_sup_level"])
					if pd.notna(latest["bsu_bpu_sup_level"])
					else None
				),
				"res_bpu_count": int(latest["res_bpu_count"]),
				"sup_bpu_count": int(latest["sup_bpu_count"]),
				"res_atr_potential": (
					float(latest["res_atr_left"])
					if pd.notna(latest["res_atr_left"])
					else None
				),
				"sup_atr_potential": (
					float(latest["sup_atr_left"])
					if pd.notna(latest["sup_atr_left"])
					else None
				),
			},
			metadata={
				"lookback": lookback,
				"atr_window": atr_window,
				"tolerance_mult": tolerance_mult,
			},
		)


registry.register(BsuBpuLevelIndicator())
