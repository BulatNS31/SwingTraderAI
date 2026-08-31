from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import pandas as pd

from swingtraderai.ml.setups.risk import build_risk
from swingtraderai.ml.setups.volume import build_volume_context
from swingtraderai.schemas.trade_setup import (
	LevelContext,
	LevelType,
	SetupSide,
	SetupType,
	SignalStrength,
	TradeSetup,
	TrendContext,
	TriggerContext,
)


def build_false_breakout_setups(
	df: pd.DataFrame,
	*,
	symbol: str,
	timeframe: str,
	trend: TrendContext,
	ticker_id: Optional[UUID] = None,
	only_last_bar: bool = True,
	require_trend_align: bool = True,
) -> List[TradeSetup]:
	"""
	Ожидает: false_breakout, fb_type, fb_depth, fb_return_bars,
	nearest_level, level_type, close, high, low, atr*
	"""
	if "false_breakout" not in df.columns:
		return []

	indices = [len(df) - 1] if only_last_bar else range(len(df))
	setups: List[TradeSetup] = []

	for i in indices:
		row = df.iloc[i]
		if int(row.get("false_breakout") or 0) != 1:
			continue

		fb_type = str(row.get("fb_type") or "")
		if fb_type == "bear_trap":
			side = SetupSide.LONG
			stype = SetupType.FALSE_BREAKOUT_BEAR_TRAP
			if require_trend_align and trend.direction.value == "down":
				continue
		elif fb_type == "bull_trap":
			side = SetupSide.SHORT
			stype = SetupType.FALSE_BREAKOUT_BULL_TRAP
			if require_trend_align and trend.direction.value == "up":
				continue
		else:
			continue

		entry = float(row["close"])
		atr = _atr(row, df)
		level_price = row.get("nearest_level")
		level_price_f = float(level_price) if pd.notna(level_price) else None

		level = LevelContext(
			near_level=level_price_f is not None,
			level_type=(
				LevelType.SUPPORT
				if row.get("level_type") == "support"
				else (
					LevelType.RESISTANCE
					if row.get("level_type") == "resistance"
					else LevelType.NONE
				)
			),
			level_price=level_price_f,
			level_strength=(
				float(row["level_strength"])
				if pd.notna(row.get("level_strength"))
				else None
			),
			source="strong_levels",
		)

		# invalidation — за экстремум ложного пробоя
		if side == SetupSide.LONG:
			swing_inv = float(row["low"]) - 0.1 * atr
		else:
			swing_inv = float(row["high"]) + 0.1 * atr

		risk = build_risk(
			side=side,
			entry=entry,
			atr=atr,
			level_price=level_price_f,
			swing_invalidation=swing_inv,
			atr_stop_mult=1.0,
			atr_target_mult=2.0,
		)

		vol = build_volume_context(row)
		depth = float(row["fb_depth"]) if pd.notna(row.get("fb_depth")) else None
		strength = 6
		if depth and depth > 1.0:
			strength += 1
		if vol.confirmed:
			strength += 1
		if level.near_level:
			strength += 1

		bar_time = _bar_time(row, df)

		setups.append(
			TradeSetup(
				ticker_id=ticker_id,
				symbol=symbol,
				timeframe=timeframe,
				bar_time=bar_time,
				side=side,
				setup_type=stype,
				trend=trend,
				level=level,
				trigger=TriggerContext(
					setup_type=stype,
					side=side,
					confirmed=True,
					details={
						"fb_type": fb_type,
						"fb_depth": depth,
						"fb_return_bars": int(row.get("fb_return_bars") or 0),
					},
				),
				volume=vol,
				risk=risk,
				composite_signal=(
					SignalStrength.BUY
					if side == SetupSide.LONG
					else SignalStrength.SELL
				),
				signal_strength=min(10, strength),
				indicators_used=["false_breakout", "levels", "atr"],
				tags=["gerchik", "false_breakout"],
			)
		)

	return setups


def _atr(row: pd.Series, df: pd.DataFrame) -> float:
	for col in ("atr14", "atr_14", "atr"):
		if col in df.columns and pd.notna(row.get(col)):
			return float(row[col])
	return max(float(row["high"]) - float(row["low"]), 1e-6)


def _bar_time(row: pd.Series, df: pd.DataFrame) -> datetime:
	for col in ("time", "date", "datetime"):
		if col in df.columns and pd.notna(row.get(col)):
			val = row[col]
			if isinstance(val, datetime):
				return val
			dt = pd.to_datetime(val)
			result: datetime = dt.to_pydatetime()
			return result
	return datetime.now(timezone.utc)
