"""Point-in-time feature engineering for ML backtests.

Only uses information available at the last bar of the provided history.
No shift(-1), no centered rolling, no future returns.

When the full project is available, prefer
swingtraderai.indicators.matrix.add_all_indicators
for parity with live inference — this module is the standalone-safe subset.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

# Canonical feature names used by FrozenModel when no custom list is provided.
DEFAULT_FEATURE_COLUMNS: List[str] = [
	"return_1",
	"return_3",
	"return_5",
	"return_10",
	"rsi_14",
	"sma_ratio_10",
	"sma_ratio_30",
	"ema_fast_slope",
	"atr_pct",
	"vol_zscore",
	"high_low_range",
]


def build_feature_frame(history: pd.DataFrame) -> pd.DataFrame:
	"""Return a feature matrix aligned to ``history`` (same index/length).

	All columns are causal (past-only). NaNs remain on the warmup head —
	callers must drop or mask them before training / inference.
	"""
	df = history.copy()
	df.columns = [c.lower() for c in df.columns]
	close = df["close"].astype(float)
	high = df["high"].astype(float) if "high" in df.columns else close
	low = df["low"].astype(float) if "low" in df.columns else close
	volume = (
		df["volume"].astype(float)
		if "volume" in df.columns
		else pd.Series(np.nan, index=df.index)
	)

	out = pd.DataFrame(index=df.index)

	for lag in (1, 3, 5, 10):
		out[f"return_{lag}"] = close.pct_change(lag)

	delta = close.diff()
	gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
	loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
	rs = gain / loss.replace(0, np.nan)
	out["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))

	sma10 = close.rolling(10, min_periods=10).mean()
	sma30 = close.rolling(30, min_periods=30).mean()
	out["sma_ratio_10"] = close / sma10 - 1.0
	out["sma_ratio_30"] = close / sma30 - 1.0

	ema_fast = close.ewm(span=9, adjust=False).mean()
	out["ema_fast_slope"] = ema_fast.pct_change(3)

	prev_close = close.shift(1)
	tr = pd.concat(
		[
			(high - low).abs(),
			(high - prev_close).abs(),
			(low - prev_close).abs(),
		],
		axis=1,
	).max(axis=1)
	atr = tr.rolling(14, min_periods=14).mean()
	out["atr_pct"] = atr / close

	vol_ma = volume.rolling(20, min_periods=5).mean()
	vol_std = volume.rolling(20, min_periods=5).std()
	out["vol_zscore"] = (volume - vol_ma) / vol_std.replace(0, np.nan)

	out["high_low_range"] = (high - low) / close.replace(0, np.nan)

	out = out.replace([np.inf, -np.inf], np.nan)
	return out


def last_feature_row(
	history: pd.DataFrame,
	feature_columns: Optional[List[str]] = None,
) -> Optional[pd.Series]:
	"""Scalar feature vector for the last bar, or None if not yet warm."""
	cols = feature_columns or DEFAULT_FEATURE_COLUMNS
	feats = build_feature_frame(history)
	missing = [c for c in cols if c not in feats.columns]
	if missing:
		return None
	row = feats[cols].iloc[-1]
	if row.isna().any():
		return None
	return row


def make_labels(
	history: pd.DataFrame,
	horizon: int = 5,
	threshold: float = 0.0,
) -> pd.Series:
	"""Binary label: 1 if forward return over ``horizon`` bars > threshold.

	WARNING: uses future data — ONLY for training-set construction, never
	as a live feature.
	"""
	close = history["close"].astype(float)
	fwd = close.shift(-horizon) / close - 1.0
	labels = (fwd > threshold).astype(float)
	labels.iloc[-horizon:] = np.nan
	return labels
