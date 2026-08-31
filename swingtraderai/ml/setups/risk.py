from __future__ import annotations

from typing import Optional

from swingtraderai.schemas.trade_setup import RiskContext, SetupSide


def build_risk(
	*,
	side: SetupSide,
	entry: float,
	atr: float,
	level_price: Optional[float] = None,
	atr_stop_mult: float = 1.0,
	atr_target_mult: float = 2.0,
	swing_invalidation: Optional[float] = None,
) -> RiskContext:
	"""
	Стоп: swing_invalidation или level ± atr_stop_mult * ATR.
	Цель: entry ± atr_target_mult * ATR (минимум R:R закладывается множителями).
	"""
	atr = max(float(atr), 1e-8)

	if side == SetupSide.LONG:
		if swing_invalidation is not None:
			invalidation = float(swing_invalidation)
		elif level_price is not None:
			invalidation = float(level_price) - atr_stop_mult * atr
		else:
			invalidation = entry - atr_stop_mult * atr
		# стоп не выше entry
		invalidation = min(invalidation, entry - 1e-6)
		target_1 = entry + atr_target_mult * atr
		target_2 = entry + (atr_target_mult * 1.5) * atr
	elif side == SetupSide.SHORT:
		if swing_invalidation is not None:
			invalidation = float(swing_invalidation)
		elif level_price is not None:
			invalidation = float(level_price) + atr_stop_mult * atr
		else:
			invalidation = entry + atr_stop_mult * atr
		invalidation = max(invalidation, entry + 1e-6)
		target_1 = entry - atr_target_mult * atr
		target_2 = entry - (atr_target_mult * 1.5) * atr
	else:
		invalidation = entry
		target_1 = target_2 = entry

	return RiskContext(
		entry=float(entry),
		invalidation=float(invalidation),
		target_1=float(target_1),
		target_2=float(target_2),
		atr=float(atr),
		atr_stop_mult=atr_stop_mult,
	)
