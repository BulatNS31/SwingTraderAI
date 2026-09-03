from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from swingtraderai.indicators.levels import add_key_levels_indicators
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


def _pivot_tf_for(timeframe: str) -> str:
	"""Подобрать timeframe для pivot points по исходному TF свечей."""
	tf = timeframe.lower().strip()
	if tf in {"1w", "1wk", "week", "w"}:
		return "M"
	if tf in {"1d", "day", "d"}:
		return "W"
	return "D"


def _find_col(df: pd.DataFrame, patterns: List[str]) -> Optional[str]:
	"""Найти первую колонку, имя которой содержит один из patterns.

	Сравнение без учёта регистра и подчёркиваний.
	Порядок patterns = приоритет (более специфичные — первыми).
	"""
	normalized: Dict[str, str] = {c: c.lower().replace("_", "") for c in df.columns}
	for pattern in patterns:
		p = pattern.lower().replace("_", "")
		for col, norm in normalized.items():
			if p in norm:
				return col
	return None


def engineer_features(df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
	"""Инженерия признаков для ML (bar-level).

	Добавляет:
	- pandas_ta индикаторы (SMA/EMA, RSI, ATR, MACD, BB)
	- ключевые уровни (fractals, S/R, pivots)
	- нормализованные дистанции до уровней
	- EMA / momentum / return / volatility / volume / time фичи

	Не добавляет target — для этого отдельный add_target().
	"""
	df = df.copy()
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	MARKET_DATA_SCHEMA.validate_base_columns(df)

	close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN
	# high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN
	# low_col = MARKET_DATA_SCHEMA.LOW_COLUMN
	time_col = MARKET_DATA_SCHEMA.TIME_COLUMN
	volume_col = MARKET_DATA_SCHEMA.VOLUME_COLUMN

	pivot_tf = _pivot_tf_for(timeframe)

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
		df.ta.atr(length=20, append=True)

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
	# Resolve column names (pandas_ta naming varies)
	# ==========================
	atr_col = _find_col(df, ["atr14", "atrr14", "atr"])
	atr20_col = _find_col(df, ["atr20", "atrr20"])
	rsi_col = _find_col(df, ["rsi14", "rsi"])

	ema9_col = _find_col(df, ["ema9"])
	ema21_col = _find_col(df, ["ema21"])
	ema50_col = _find_col(df, ["ema50"])
	ema200_col = _find_col(df, ["ema200"])

	macd_col = _find_col(df, ["macd_12_26_9", "macd"])
	macdh_col = _find_col(df, ["macdh", "macd_hist"])

	bb_upper = _find_col(df, ["bbu"])
	bb_lower = _find_col(df, ["bbl"])

	if not atr_col or not rsi_col:
		raise ValueError(
			f"ATR/RSI не найдены после расчёта индикаторов. Колонки: {list(df.columns)}"
		)

	# ==========================
	# Distance to Levels (ATR-normalized)
	# ==========================
	if "pp" in df.columns:
		df["close_to_pp"] = (df[close_col] - df["pp"]) / df[atr_col]

	if "r1" in df.columns:
		df["dist_to_r1"] = (df["r1"] - df[close_col]) / df[atr_col]

	if "s1" in df.columns:
		df["dist_to_s1"] = (df[close_col] - df["s1"]) / df[atr_col]

	# Fractals: shift(2) — фрактал с window=2 подтверждается через 2 бара
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
		if col is not None:
			df[f"{name}_dist"] = (df[close_col] - df[col]) / df[atr_col]
			df[f"{name}_slope"] = df[col].pct_change(3)
			df[f"price_above_{name}"] = (df[close_col] > df[col]).astype(int)

	if ema9_col and ema21_col:
		df["ema9_gt_ema21"] = (df[ema9_col] > df[ema21_col]).astype(int)
	if ema50_col and ema200_col:
		df["ema50_gt_ema200"] = (df[ema50_col] > df[ema200_col]).astype(int)

	# ==========================
	# Momentum Features
	# ==========================
	df["rsi_value"] = df[rsi_col]
	df["rsi_delta_3"] = df[rsi_col].diff(3)
	df["rsi_delta_5"] = df[rsi_col].diff(5)
	df["rsi_mom"] = df[rsi_col].diff(5)

	df["rsi_overbought"] = (df[rsi_col] > 70).astype(int)
	df["rsi_oversold"] = (df[rsi_col] < 30).astype(int)

	if macd_col:
		df["macd_value"] = df[macd_col]
	if macdh_col:
		df["macd_hist"] = df[macdh_col]
		df["macd_mom"] = df[macdh_col].diff(3)

	# ==========================
	# Return Features
	# ==========================
	for lag in [1, 3, 5, 10, 20]:
		df[f"return_{lag}"] = df[close_col].pct_change(lag)

	# ==========================
	# Volatility Features
	# ==========================
	df["atr_pct"] = df[atr_col] / df[close_col]

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
	if volume_col in df.columns:
		volume_ma20 = df[volume_col].rolling(20).mean()
		volume_std20 = df[volume_col].rolling(20).std()

		df["relative_volume"] = df[volume_col] / volume_ma20
		df["volume_zscore"] = (df[volume_col] - volume_ma20) / volume_std20
		df["volume_spike"] = (df["volume_zscore"] > 2.0).astype(int)
	else:
		df["relative_volume"] = np.nan
		df["volume_zscore"] = np.nan
		df["volume_spike"] = 0

	# ==========================
	# Interaction / regime features
	# ==========================
	if "dist_to_r1" in df.columns:
		df["dist_to_r1_mom"] = df["dist_to_r1"] * df["rsi_delta_3"]
	if "dist_to_s1" in df.columns:
		df["dist_to_s1_mom"] = df["dist_to_s1"] * df["rsi_delta_3"]

	if ema9_col and ema200_col:
		df["trend_strength"] = (df[ema9_col] - df[ema200_col]).abs() / df[atr_col]

	df["high_volatility"] = (df["atr_pct"] > df["atr_pct"].rolling(100).mean()).astype(
		int
	)

	# Time features (полезны для MOEX/акции, для crypto можно отключить)
	if time_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[time_col]):
		df["hour"] = df[time_col].dt.hour
		df["dayofweek"] = df[time_col].dt.dayofweek
		# Заглушка под MOEX/EU сессию, для crypto не информативно
		df["is_session_open"] = df["hour"].between(9, 11).astype(int)

	# ==========================
	# Cleanup
	# ==========================
	# Уровни «живут», пока не сменятся — ffill для feature matrix
	for col in ("pp", "fractal_high", "fractal_low", "r1", "s1"):
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
	"""Разметка таргета для bar-level ML.

	Triple Barrier (use_triple_barrier=True, рекомендуется):
	PT = close + ATR * pt_mult
	SL = close - ATR * sl_mult
	В горизонте horizon баров:
	high >= PT → 1
	low  <= SL → 0
	иначе → 1, если close[t+h] > close[t], иначе 0

	Простой режим (use_triple_barrier=False):
	target = 1, если future_return > threshold
	(или > 1.25 * atr_pct, если threshold is None)

	Важно: это bar-level таргет, не setup-level (см. ml/setup_dataset.py).
	"""
	df = df.copy()
	close_col = MARKET_DATA_SCHEMA.CLOSE_COLUMN
	high_col = MARKET_DATA_SCHEMA.HIGH_COLUMN
	low_col = MARKET_DATA_SCHEMA.LOW_COLUMN

	atr_col = _find_col(df, ["atr14", "atrr14", "atr"])
	if atr_col is None:
		raise ValueError("ATR column not found — сначала вызовите engineer_features()")

	if use_triple_barrier:
		closes = df[close_col].to_numpy(dtype=float)
		highs = df[high_col].to_numpy(dtype=float)
		lows = df[low_col].to_numpy(dtype=float)
		atrs = df[atr_col].to_numpy(dtype=float)

		n = len(df)
		# NaN на хвосте и при битом ATR — не нули (иначе ложные лейблы)
		targets = np.full(n, np.nan)

		for i in range(n - horizon):
			atr_i = atrs[i]
			if np.isnan(atr_i) or atr_i <= 0:
				continue
			if np.isnan(closes[i]):
				continue

			pt_level = closes[i] + atr_i * pt_mult
			sl_level = closes[i] - atr_i * sl_mult

			hit = False
			for j in range(1, horizon + 1):
				# Порядок: сначала PT, потом SL.
				# Если в одном баре пробиты оба — засчитываем PT (long-bias).
				if highs[i + j] >= pt_level:
					targets[i] = 1
					hit = True
					break
				if lows[i + j] <= sl_level:
					targets[i] = 0
					hit = True
					break

			if not hit:
				# Барьер не достигнут — направление по close на горизонте
				targets[i] = int(closes[i + horizon] > closes[i])

		df["target"] = targets
		df["future_return"] = df[close_col].shift(-horizon) / df[close_col] - 1
	else:
		future_return = df[close_col].shift(-horizon) / df[close_col] - 1
		df["future_return"] = future_return

		if threshold is not None:
			df["target"] = (future_return > threshold).astype(float)
		else:
			atr_threshold = (df[atr_col] / df[close_col]) * 1.25
			df["target"] = (future_return > atr_threshold).astype(float)

		# Хвост без будущего — NaN
		df.loc[df.index[-horizon:], "target"] = np.nan

	return df.dropna(subset=["target"]).reset_index(drop=True)


def add_all_indicators(df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
	"""Главная точка входа: только features, без target.

	Используется в inference и в scanner pipeline.
	Для обучения дополнительно вызывайте add_target().
	"""
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	MARKET_DATA_SCHEMA.validate_base_columns(df)

	df = engineer_features(df, timeframe=timeframe)
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	return df
