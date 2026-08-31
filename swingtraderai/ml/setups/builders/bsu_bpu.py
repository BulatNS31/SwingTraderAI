# swingtraderai/setups/builders/bsu_bpu.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

import pandas as pd

from swingtraderai.indicators.base import calculate_atr
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


def build_bsu_bpu_setups(
	df: pd.DataFrame,
	*,
	symbol: str,
	timeframe: str,
	trend: TrendContext,
	ticker_id: Optional[UUID] = None,
	only_last_bar: bool = True,
	min_bpu: int = 2,
	max_dist_atr: float = 0.8,
) -> List[TradeSetup]:
	"""
	Реакция у БСУ/БПУ: цена близко к уровню, есть запас хода в ATR.
	Ожидает колонки detect_bsu_bpu_levels + close, high, low, atr*.
	"""
	if "bsu_bpu_sup_level" not in df.columns and "bsu_bpu_res_level" not in df.columns:
		return []

	indices = [len(df) - 1] if only_last_bar else range(len(df))
	setups: List[TradeSetup] = []

	for i in indices:
		row = df.iloc[i]
		atr = _atr(row, df, i)
		close = float(row["close"])

		# Long у поддержки
		sup = row.get("bsu_bpu_sup_level")
		sup_bpu = int(row.get("sup_bpu_count") or 0)
		if pd.notna(sup) and sup_bpu >= min_bpu:
			dist_atr = abs(close - float(sup)) / atr
			if dist_atr <= max_dist_atr and trend.direction.value != "down":
				setups.append(
					_make_setup(
						row=row,
						df=df,
						i=i,
						symbol=symbol,
						timeframe=timeframe,
						trend=trend,
						ticker_id=ticker_id,
						side=SetupSide.LONG,
						level_price=float(sup),
						level_type=LevelType.SUPPORT,
						bpu=sup_bpu,
						atr_pot=row.get("sup_atr_left"),
						atr=atr,
					)
				)

		# Short у сопротивления
		res = row.get("bsu_bpu_res_level")
		res_bpu = int(row.get("res_bpu_count") or 0)
		if pd.notna(res) and res_bpu >= min_bpu:
			dist_atr = abs(close - float(res)) / atr
			if dist_atr <= max_dist_atr and trend.direction.value != "up":
				setups.append(
					_make_setup(
						row=row,
						df=df,
						i=i,
						symbol=symbol,
						timeframe=timeframe,
						trend=trend,
						ticker_id=ticker_id,
						side=SetupSide.SHORT,
						level_price=float(res),
						level_type=LevelType.RESISTANCE,
						bpu=res_bpu,
						atr_pot=row.get("res_atr_left"),
						atr=atr,
					)
				)

	return setups


def _make_setup(
	*,
	row: pd.Series,
	df: pd.DataFrame,
	i: int,
	symbol: str,
	timeframe: str,
	trend: TrendContext,
	ticker_id: Optional[UUID],
	side: SetupSide,
	level_price: float,
	level_type: LevelType,
	bpu: int,
	atr_pot: object,
	atr: float,
) -> TradeSetup:
	entry = float(row["close"])
	atr_potential = (
		float(str(atr_pot)) if atr_pot is not None and pd.notna(atr_pot) else None
	)

	level = LevelContext(
		near_level=True,
		level_type=level_type,
		level_price=level_price,
		level_strength=float(bpu),
		bpu_count=bpu,
		atr_potential=atr_potential,
		dist_to_level_pct=(entry - level_price) / level_price,
		source="bsu_bpu",
	)

	if side == SetupSide.LONG:
		swing_inv = min(float(row["low"]), level_price) - 0.3 * atr
	else:
		swing_inv = max(float(row["high"]), level_price) + 0.3 * atr

	# цель: если есть запас хода в ATR — используем его
	target_mult = min(max(atr_potential or 2.0, 1.5), 3.0)

	risk = build_risk(
		side=side,
		entry=entry,
		atr=atr,
		level_price=level_price,
		swing_invalidation=swing_inv,
		atr_stop_mult=0.5,
		atr_target_mult=target_mult,
	)

	vol = build_volume_context(row)
	strength = 5 + min(bpu, 3)
	if vol.confirmed:
		strength += 1

	return TradeSetup(
		ticker_id=ticker_id,
		symbol=symbol,
		timeframe=timeframe,
		bar_time=_bar_time(row, df),
		side=side,
		setup_type=SetupType.BSU_BPU_REACTION,
		trend=trend,
		level=level,
		trigger=TriggerContext(
			setup_type=SetupType.BSU_BPU_REACTION,
			side=side,
			confirmed=True,
			details={"bpu_count": bpu, "atr_potential": atr_potential},
		),
		volume=vol,
		risk=risk,
		composite_signal=(
			SignalStrength.BUY if side == SetupSide.LONG else SignalStrength.SELL
		),
		signal_strength=min(10, strength),
		indicators_used=["bsu_bpu_levels", "atr"],
		tags=["gerchik", "bsu_bpu"],
	)


def _atr(row: pd.Series, df: pd.DataFrame, i: int) -> float:
	"""Сначала готовые колонки, иначе calculate_atr из indicators.base."""
	for col in ("atr14", "atr_14", "atr"):
		if col in df.columns and pd.notna(row.get(col)):
			val = float(row[col])
			if val > 0:
				return val

	atr_series = calculate_atr(df, window=14)
	val = atr_series.iloc[i]
	if pd.notna(val) and float(val) > 0:
		return float(val)

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
