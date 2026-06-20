from typing import List, Optional

import numpy as np
import pandas as pd

from swingtraderai.indicators.levels import add_key_levels_indicators
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


def engineer_features(df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
	"""
	Улучшенная инженерия признаков для повышения AUC.
	"""

	df = df.copy()

	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	MARKET_DATA_SCHEMA.validate_base_columns(df)

	close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN
	time_col = MARKET_DATA_SCHEMA.TIME_COLUMN

	# Pivot timeframe для уровней
	pivot_tf = "M" if "W" in timeframe.upper() or "M" in timeframe.upper() else "D"

	# ==========================
	# Technical Indicators
	# ==========================
	try:
		df.ta.sma(length=10, append=True)
		df.ta.sma(length=20, append=True)
		df.ta.sma(length=50, append=True)

		df.ta.ema(length=9, append=True)
		df.ta.ema(length=21, append=True)
		df.ta.ema(length=50, append=True)
		df.ta.ema(length=200, append=True)

		df.ta.rsi(length=14, append=True)
		df.ta.atr(length=14, append=True)
		df.ta.atr(length=20, append=True)  # дополнительный ATR

		df.ta.macd(append=True)
		df.ta.bbands(length=20, append=True)

	except Exception as e:
		raise RuntimeError(f"Ошибка при расчёте индикаторов pandas_ta: {e}") from e

	# ==========================
	# Key Levels
	# ==========================
	df = add_key_levels_indicators(
		df,
		fractal_window=2,
		sr_window=100,
		pivot_tf=pivot_tf,
	)

	# ==========================
	# Column Finder - ИСПРАВЛЕНА АННОТАЦИЯ
	# ==========================
	def find_col(patterns: List[str]) -> Optional[str]:
		for pattern in patterns:
			matches = [
				c for c in df.columns if pattern.lower() in c.lower().replace("_", "")
			]
			if matches:
				return str(matches[0])  # Явное приведение к str
		return None

	atr_col = find_col(["atr14", "atr"])
	atr20_col = find_col(["atr20"])
	rsi_col = find_col(["rsi14", "rsi"])

	ema9_col = find_col(["ema9"])
	ema21_col = find_col(["ema21"])
	ema50_col = find_col(["ema50"])
	ema200_col = find_col(["ema200"])

	macd_col = find_col(["macd_12_26_9", "macd"])
	macdh_col = find_col(["macdh", "macd_hist"])

	bb_upper = find_col(["bbu"])
	bb_lower = find_col(["bbl"])

	if not atr_col or not rsi_col:
		raise ValueError(f"ATR/RSI не найдены. Колонки: {list(df.columns)}")

	# ==========================
	# Distance to Levels (ATR-normalized)
	# ==========================
	if "pp" in df.columns:
		df["close_to_pp"] = (df[close_col] - df["pp"]) / df[atr_col]

	if "r1" in df.columns:
		df["dist_to_r1"] = (df["r1"] - df[close_col]) / df[atr_col]

	if "s1" in df.columns:
		df["dist_to_s1"] = (df[close_col] - df["s1"]) / df[atr_col]

	# Fractals (с lag для защиты от look-ahead)
	if "fractal_high" in df.columns:
		df["dist_to_last_fractal_high"] = (
			df["fractal_high"].shift(2).ffill() - df[close_col]
		) / df[atr_col]

	if "fractal_low" in df.columns:
		df["dist_to_last_fractal_low"] = (
			df[close_col] - df["fractal_low"].shift(2).ffill()
		) / df[atr_col]

	# ==========================
	# EMA Features
	# ==========================
	ema_features = {
		"ema9": ema9_col,
		"ema21": ema21_col,
		"ema50": ema50_col,
		"ema200": ema200_col,
	}

	for name, col in ema_features.items():
		if col:
			df[f"{name}_dist"] = (df[close_col] - df[col]) / df[atr_col]
			df[f"{name}_slope"] = df[col].pct_change(3)
			df[f"price_above_{name}"] = (df[close_col] > df[col]).astype(int)

	# Crossovers
	if ema9_col and ema21_col:
		df["ema9_gt_ema21"] = (df[ema9_col] > df[ema21_col]).astype(int)
	if ema50_col and ema200_col:
		df["ema50_gt_ema200"] = (df[ema50_col] > df[ema200_col]).astype(int)

	# ==========================
	# Momentum Features (улучшено)
	# ==========================
	df["rsi_value"] = df[rsi_col]
	df["rsi_delta_3"] = df[rsi_col].diff(3)
	df["rsi_delta_5"] = df[rsi_col].diff(5)  # новое
	df["rsi_mom"] = df[rsi_col].diff(5)  # momentum of RSI

	df["rsi_overbought"] = (df[rsi_col] > 70).astype(int)
	df["rsi_oversold"] = (df[rsi_col] < 30).astype(int)

	if macd_col:
		df["macd_value"] = df[macd_col]
	if macdh_col:
		df["macd_hist"] = df[macdh_col]
		df["macd_mom"] = df[macdh_col].diff(3)  # новое

	# ==========================
	# Return Features (сократили)
	# ==========================
	for lag in [1, 3, 5, 10, 20]:
		df[f"return_{lag}"] = df[close_col].pct_change(lag)

	# ==========================
	# Volatility Features
	# ==========================
	df["atr_pct"] = df[atr_col] / df[close_col]
	# ИСПРАВЛЕНА ОШИБКА: используем Optional[str]
	if atr20_col:
		df["atr20_pct"] = df[atr20_col] / df[close_col]
	else:
		df["atr20_pct"] = df["atr_pct"]

	df["volatility_regime"] = df["atr_pct"] / df["atr_pct"].rolling(50).mean()
	df["vol_regime_change"] = df["volatility_regime"].diff(5)

	if bb_upper and bb_lower:
		df["bb_width"] = (df[bb_upper] - df[bb_lower]) / df[close_col]
		df["squeeze"] = (df["bb_width"] < df["bb_width"].rolling(20).mean()).astype(int)

	# ==========================
	# Volume Features
	# ==========================
	volume_ma20 = df["volume"].rolling(20).mean()
	volume_std20 = df["volume"].rolling(20).std()

	df["relative_volume"] = df["volume"] / volume_ma20
	df["volume_zscore"] = (df["volume"] - volume_ma20) / volume_std20
	df["volume_spike"] = (df["volume_zscore"] > 2.0).astype(int)

	# ==========================
	# Новые мощные признаки
	# ==========================
	# Momentum of distance to levels
	if "dist_to_r1" in df.columns:
		df["dist_to_r1_mom"] = df["dist_to_r1"] * df["rsi_delta_3"]
	if "dist_to_s1" in df.columns:
		df["dist_to_s1_mom"] = df["dist_to_s1"] * df["rsi_delta_3"]

	# Trend strength
	if ema9_col and ema200_col:
		df["trend_strength"] = abs(df[ema9_col] - df[ema200_col]) / df[atr_col]

	# Regime features
	df["high_volatility"] = (df["atr_pct"] > df["atr_pct"].rolling(100).mean()).astype(
		int
	)

	# Time features (очень полезны)
	if pd.api.types.is_datetime64_any_dtype(df[time_col]):
		df["hour"] = df[time_col].dt.hour
		df["dayofweek"] = df[time_col].dt.dayofweek
		df["is_session_open"] = df["hour"].between(9, 11).astype(int)

	# ==========================
	# Cleanup
	# ==========================
	critical_cols = ["pp", "fractal_high", "fractal_low", "r1", "s1"]
	for col in critical_cols:
		if col in df.columns:
			df[col] = df[col].ffill()

	df = df.replace([np.inf, -np.inf], np.nan)

	return df


def add_target(
	df: pd.DataFrame,
	horizon: int = 10,
	pt_mult: float = 1.5,
	sl_mult: float = 1.0,
	use_triple_barrier: bool = True,
	threshold: Optional[float] = None,
) -> pd.DataFrame:
	"""
	Улучшенный таргет: Triple Barrier (рекомендуется)

	df: DataFrame с данными
	horizon: Горизонт прогноза
	pt_mult: Множитель для take-profit (в ATR)
	sl_mult: Множитель для stop-loss (в ATR)
	use_triple_barrier: Использовать Triple Barrier
	threshold: Порог для простого таргета (если не используется Triple Barrier)
	"""
	df = df.copy()
	close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN

	atr_col = next(
		(
			c
			for c in df.columns
			if any(p in c.lower().replace("_", "") for p in ("atr14", "atrr14", "atr"))
		),
		None,
	)
	if atr_col is None:
		raise ValueError("ATR column not found")

	if use_triple_barrier:
		closes = df[close_col].values
		highs = df["high"].values
		lows = df["low"].values
		atrs = df[atr_col].values

		targets = np.zeros(len(df), dtype=int)

		for i in range(len(df) - horizon):
			pt_level = closes[i] + atrs[i] * pt_mult
			sl_level = closes[i] - atrs[i] * sl_mult

			executed = False
			for j in range(1, horizon + 1):
				if highs[i + j] >= pt_level:
					targets[i] = 1
					executed = True
					break
				if lows[i + j] <= sl_level:
					targets[i] = 0
					executed = True
					break

			if not executed:
				targets[i] = int(closes[i + horizon] > closes[i])

		df["target"] = targets
		df["future_return"] = df[close_col].shift(-horizon) / df[close_col] - 1
	else:
		future_return = df[close_col].shift(-horizon) / df[close_col] - 1

		if threshold is not None:
			df["target"] = (future_return > threshold).astype(int)
		else:
			atr_threshold = (df[atr_col] / df[close_col]) * 1.25
			df["target"] = (future_return > atr_threshold).astype(int)

		df["future_return"] = future_return

	return df.dropna(subset=["target"]).reset_index(drop=True)


def add_all_indicators(df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
	"""Главная точка входа"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	MARKET_DATA_SCHEMA.validate_base_columns(df)

	df = engineer_features(df, timeframe=timeframe)
	df = MARKET_DATA_SCHEMA.normalize_columns(df)

	return df
