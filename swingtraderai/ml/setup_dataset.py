from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from swingtraderai.ml.setups.scanner import SetupScanner
from swingtraderai.schemas.trade_setup import SetupSide, TradeSetup


def label_setup_outcome(
	df: pd.DataFrame,
	setup: TradeSetup,
	*,
	horizon: int = 15,
	mode: str = "rr",  # "rr" | "atr"
	atr_mult: float = 1.5,
) -> Optional[int]:
	"""
	1 = цель достигнута раньше (или без) стопа в окне horizon.
	0 = стоп / цель не достигнута.
	None = нельзя разметить (мало баров вперёд).

	mode="rr":  target_1 / invalidation из setup.risk
	mode="atr":  long: +atr_mult*ATR, short: -atr_mult*ATR; stop = invalidation
	"""
	if "time" not in df.columns and "close" not in df.columns:
		return None

	# индекс бара setup
	i = _find_bar_index(df, setup)
	if i is None or i + 1 >= len(df):
		return None

	end = min(i + horizon, len(df) - 1)
	if end <= i:
		return None

	future = df.iloc[i + 1 : end + 1]
	entry = setup.risk.entry
	side = setup.side

	if mode == "rr":
		target = setup.risk.target_1
		stop = setup.risk.invalidation
		if target is None or stop is None:
			return None
	else:
		atr = setup.risk.atr or _row_atr(df.iloc[i])
		stop = setup.risk.invalidation
		if side == SetupSide.LONG:
			target = entry + atr_mult * atr
		else:
			target = entry - atr_mult * atr

	hit_tp = False
	hit_sl = False

	for _, bar in future.iterrows():
		high = float(bar["high"])
		low = float(bar["low"])

		if side == SetupSide.LONG:
			if low <= stop:
				hit_sl = True
				break
			if high >= target:
				hit_tp = True
				break
		else:
			if high >= stop:
				hit_sl = True
				break
			if low <= target:
				hit_tp = True
				break

	if hit_tp:
		return 1
	if hit_sl:
		return 0
	# не дошли ни до TP, ни до SL — считаем неуспехом (консервативно)
	return 0


def setup_to_features(setup: TradeSetup) -> Dict[str, float]:
	"""Числовой вектор для XGBoost (без утечки target)."""
	t = setup.trend
	lv = setup.level
	v = setup.volume
	r = setup.risk
	tr = setup.trigger

	trend_map = {"up": 1.0, "down": -1.0, "sideways": 0.0, "unknown": 0.0}
	side_map = {"long": 1.0, "short": -1.0, "none": 0.0}
	level_map = {"support": 1.0, "resistance": -1.0, "none": 0.0}

	# one-hot setup_type (стабильный набор)
	types = [
		"bullish_divergence",
		"bearish_divergence",
		"false_breakout_bear_trap",
		"false_breakout_bull_trap",
		"bsu_bpu_reaction",
	]
	type_feats = {
		f"type_{k}": 1.0 if setup.setup_type.value == k else 0.0 for k in types
	}

	feats: Dict[str, float] = {
		"side": side_map.get(setup.side.value, 0.0),
		"signal_strength": float(setup.signal_strength),
		"trend_dir": trend_map.get(t.direction.value, 0.0),
		"price_above_ema200": _bool(t.price_above_ema200),
		"ema9_gt_ema21": _bool(t.ema9_gt_ema21),
		"near_level": 1.0 if lv.near_level else 0.0,
		"level_type": level_map.get(lv.level_type.value, 0.0),
		"level_strength": float(lv.level_strength or 0.0),
		"dist_to_level_pct": float(lv.dist_to_level_pct or 0.0),
		"bpu_count": float(lv.bpu_count or 0.0),
		"atr_potential": float(lv.atr_potential or 0.0),
		"volume_confirmed": 1.0 if v.confirmed else 0.0,
		"volume_ratio": float(v.volume_ratio or 1.0),
		"volume_zscore": float(v.volume_zscore or 0.0),
		"reward_risk": float(r.reward_risk or 0.0),
		"stop_distance_pct": (
			float(r.stop_distance / r.entry) if r.stop_distance and r.entry else 0.0
		),
		"atr_pct": float((r.atr or 0.0) / r.entry) if r.entry else 0.0,
		# details
		"fb_depth": float(tr.details.get("fb_depth") or 0.0),
		"fb_return_bars": float(tr.details.get("fb_return_bars") or 0.0),
		**type_feats,
	}
	return feats


def build_setup_dataset(
	df: pd.DataFrame,
	*,
	symbol: str,
	timeframe: str = "1D",
	horizon: int = 15,
	label_mode: str = "rr",
	atr_mult: float = 1.5,
) -> Tuple[pd.DataFrame, pd.Series]:
	"""
	Сканирует всю историю (only_last_bar=False), размечает, возвращает X, y.
	"""
	scanner = SetupScanner(
		use_divergence=True,
		use_false_breakout=True,
		use_bsu_bpu=True,
		require_trend_align=True,
		only_last_bar=False,
	)
	prepared = scanner.prepare(df, timeframe=timeframe)
	result = scanner.scan(
		prepared,
		symbol=symbol,
		timeframe=timeframe,
		prepare=False,
	)

	rows: List[Dict[str, float]] = []
	labels: List[int] = []

	for setup in result.setups:
		y = label_setup_outcome(
			prepared,
			setup,
			horizon=horizon,
			mode=label_mode,
			atr_mult=atr_mult,
		)
		if y is None:
			continue
		rows.append(setup_to_features(setup))
		labels.append(y)

	if not rows:
		return pd.DataFrame(), pd.Series(dtype=int)

	X = pd.DataFrame(rows).fillna(0.0)
	y = pd.Series(labels, name="target")
	return X, y


def _find_bar_index(df: pd.DataFrame, setup: TradeSetup) -> Optional[int]:
	if "time" in df.columns:
		times = pd.to_datetime(df["time"])
		target = pd.Timestamp(setup.bar_time)
		# без tz для сравнения
		if getattr(target, "tzinfo", None) is not None:
			target = target.tz_localize(None)
		if times.dt.tz is not None:
			times = times.dt.tz_localize(None)
		matches = np.where(times == target)[0]
		if len(matches):
			return int(matches[-1])
		# ближайший
		deltas = (times - target).abs()
		return int(deltas.argmin())
	return None


def _row_atr(row: pd.Series) -> float:
	for col in ("atr14", "atr_14", "atr"):
		if col in row.index and pd.notna(row.get(col)):
			return float(row[col])
	return max(float(row.get("high", 0)) - float(row.get("low", 0)), 1e-6)


def _bool(v: Optional[bool]) -> float:
	if v is None:
		return 0.0
	return 1.0 if v else 0.0
