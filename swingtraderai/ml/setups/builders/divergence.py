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


def build_divergence_setups(
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
	Ожидает колонки:
	bullish_divergence, bearish_divergence (и опционально *_macd),
	close, high, low, atr14 / atr, time,
	nearest_level, level_type, level_strength (опционально)
	"""
	needed = {"close", "high", "low"}
	if not needed.issubset(df.columns):
		return []

	indices = [len(df) - 1] if only_last_bar else range(len(df))
	setups: List[TradeSetup] = []

	for i in indices:
		if i < 0 or i >= len(df):
			continue
		row = df.iloc[i]
		bull = bool(row.get("bullish_divergence", False)) or bool(
			row.get("bullish_divergence_macd", False)
		)
		bear = bool(row.get("bearish_divergence", False)) or bool(
			row.get("bearish_divergence_macd", False)
		)
		if not bull and not bear:
			continue

		if bull:
			side = SetupSide.LONG
			stype = SetupType.BULLISH_DIVERGENCE
			if require_trend_align and trend.direction.value == "down":
				continue
		else:
			side = SetupSide.SHORT
			stype = SetupType.BEARISH_DIVERGENCE
			if require_trend_align and trend.direction.value == "up":
				continue

		entry = float(row["close"])
		atr = _atr(row, df, i)
		level = _level_from_row(row, side)
		risk = build_risk(
			side=side,
			entry=entry,
			atr=atr,
			level_price=level.level_price,
			swing_invalidation=(
				float(row["low"]) if side == SetupSide.LONG else float(row["high"])
			),
			atr_stop_mult=0.5,
			atr_target_mult=2.0,
		)

		osc = "rsi"
		if bool(row.get("bullish_divergence_macd", False)) or bool(
			row.get("bearish_divergence_macd", False)
		):
			osc = "macd"

		strength = _strength(
			trend_aligned=True, volume_ok=False, near_level=level.near_level
		)
		vol = build_volume_context(row)
		if vol.confirmed:
			strength = min(10, strength + 1)

		bar_time = _bar_time(row, df, i)

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
					details={"oscillator": osc},
				),
				volume=vol,
				risk=risk,
				composite_signal=(
					SignalStrength.BUY
					if side == SetupSide.LONG
					else SignalStrength.SELL
				),
				signal_strength=strength,
				indicators_used=["divergence", "atr", "ema"],
				tags=["nayman", "divergence"],
			)
		)

	return setups


def _atr(row: pd.Series, df: pd.DataFrame, i: int) -> float:
	for col in ("atr14", "atr_14", "atr"):
		if col in df.columns and pd.notna(row.get(col)):
			return float(row[col])
	return max(float(row["high"]) - float(row["low"]), 1e-6)


def _level_from_row(row: pd.Series, side: SetupSide) -> LevelContext:
	price = row.get("nearest_level")
	ltype = row.get("level_type", "")
	strength = row.get("level_strength")

	if price is None or (isinstance(price, float) and pd.isna(price)):
		# fallback BSU/BPU
		if side == SetupSide.LONG and pd.notna(row.get("bsu_bpu_sup_level")):
			return LevelContext(
				near_level=True,
				level_type=LevelType.SUPPORT,
				level_price=float(row["bsu_bpu_sup_level"]),
				bpu_count=int(row.get("sup_bpu_count") or 0),
				atr_potential=(
					float(row["sup_atr_left"])
					if pd.notna(row.get("sup_atr_left"))
					else None
				),
				source="bsu_bpu",
			)
		if side == SetupSide.SHORT and pd.notna(row.get("bsu_bpu_res_level")):
			return LevelContext(
				near_level=True,
				level_type=LevelType.RESISTANCE,
				level_price=float(row["bsu_bpu_res_level"]),
				bpu_count=int(row.get("res_bpu_count") or 0),
				atr_potential=(
					float(row["res_atr_left"])
					if pd.notna(row.get("res_atr_left"))
					else None
				),
				source="bsu_bpu",
			)
		return LevelContext()

	lt = LevelType.NONE
	if ltype == "support":
		lt = LevelType.SUPPORT
	elif ltype == "resistance":
		lt = LevelType.RESISTANCE

	close = float(row["close"])
	lp = float(price)
	return LevelContext(
		near_level=True,
		level_type=lt,
		level_price=lp,
		level_strength=(
			float(strength) if strength is not None and pd.notna(strength) else None
		),
		dist_to_level_pct=(close - lp) / lp if lp else None,
		source="strong_levels",
	)


def _strength(*, trend_aligned: bool, volume_ok: bool, near_level: bool) -> int:
	s = 5
	if trend_aligned:
		s += 1
	if near_level:
		s += 1
	if volume_ok:
		s += 1
	return min(10, s)


def _bar_time(row: pd.Series, df: pd.DataFrame, i: int) -> datetime:
	for col in ("time", "date", "datetime"):
		if col in df.columns and pd.notna(row.get(col)):
			val = row[col]
			if isinstance(val, datetime):
				return val
			dt = pd.to_datetime(val)
			result: datetime = dt.to_pydatetime()
			return result
	return datetime.now(timezone.utc)
