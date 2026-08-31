from __future__ import annotations

import pandas as pd

from swingtraderai.schemas.trade_setup import TrendContext, TrendDirection


def detect_trend(df: pd.DataFrame, lookback_structure: int = 20) -> TrendContext:
	"""
	Простой детерминированный тренд по EMA + структуре HH/HL.
	Ожидает колонки: close, и желательно ema9, ema21, ema200 / price_above_ema200.
	"""
	if df.empty or "close" not in df.columns:
		return TrendContext(direction=TrendDirection.UNKNOWN)

	row = df.iloc[-1]
	close = float(row["close"])

	price_above_ema200 = None
	if "price_above_ema200" in df.columns and pd.notna(row.get("price_above_ema200")):
		price_above_ema200 = bool(row["price_above_ema200"])
	elif "ema200" in df.columns and pd.notna(row.get("ema200")):
		price_above_ema200 = close > float(row["ema200"])

	ema9_gt_ema21 = None
	if "ema9_gt_ema21" in df.columns and pd.notna(row.get("ema9_gt_ema21")):
		ema9_gt_ema21 = bool(row["ema9_gt_ema21"])
	elif "ema9" in df.columns and "ema21" in df.columns:
		if pd.notna(row.get("ema9")) and pd.notna(row.get("ema21")):
			ema9_gt_ema21 = float(row["ema9"]) > float(row["ema21"])

	structure = _structure_label(df, lookback=lookback_structure)

	# Правила направления
	direction = TrendDirection.SIDEWAYS
	if price_above_ema200 is True and ema9_gt_ema21 is True:
		direction = TrendDirection.UP
	elif price_above_ema200 is False and ema9_gt_ema21 is False:
		direction = TrendDirection.DOWN
	elif price_above_ema200 is True:
		direction = TrendDirection.UP
	elif price_above_ema200 is False:
		direction = TrendDirection.DOWN

	if structure == "HH_HL" and direction != TrendDirection.DOWN:
		direction = TrendDirection.UP
	elif structure == "LH_LL" and direction != TrendDirection.UP:
		direction = TrendDirection.DOWN

	return TrendContext(
		direction=direction,
		price_above_ema200=price_above_ema200,
		ema9_gt_ema21=ema9_gt_ema21,
		structure=structure,
	)


def _structure_label(df: pd.DataFrame, lookback: int = 20) -> str | None:
	if len(df) < lookback + 2 or "high" not in df.columns or "low" not in df.columns:
		return None

	window = df.iloc[-lookback:]
	mid = lookback // 2
	first_high = window["high"].iloc[:mid].max()
	second_high = window["high"].iloc[mid:].max()
	first_low = window["low"].iloc[:mid].min()
	second_low = window["low"].iloc[mid:].min()

	hh = second_high > first_high
	hl = second_low > first_low
	lh = second_high < first_high
	ll = second_low < first_low

	if hh and hl:
		return "HH_HL"
	if lh and ll:
		return "LH_LL"
	return "mixed"
