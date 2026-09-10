"""Примитивы выполнения:
заполнение, разрешение SL/TP, политика неоднозначных баров.

Отделяет логику «заказ → заполнение»
от генерации сигналов и состояния позиции.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from swingtraderai.backtesting.models import ExitReason, Side

from .config import AmbiguousBarPolicy, BacktestConfig
from .costs import apply_slippage_to_price, commission_cost


@dataclass(frozen=True)
class Fill:
	"""Result of an order fill."""

	price: float
	quantity: float
	commission: float
	slippage_amount: float  # absolute cash cost of slippage
	side: Side
	is_entry: bool


@dataclass(frozen=True)
class ExitCheckResult:
	"""Outcome of checking SL / TP / trailing on the current bar."""

	hit: bool
	reason: Optional[ExitReason] = None
	fill_price: Optional[float] = None


def create_entry_fill(
	raw_price: float,
	quantity: float,
	side: Side,
	config: BacktestConfig,
) -> Fill:
	"""Build an entry Fill with slippage and commission applied."""
	filled_price = apply_slippage_to_price(
		raw_price, side.value, is_entry=True, config=config
	)
	notional = filled_price * quantity
	comm = commission_cost(notional, config)
	slip_amt = abs(filled_price - raw_price) * quantity
	return Fill(
		price=filled_price,
		quantity=quantity,
		commission=comm,
		slippage_amount=slip_amt,
		side=side,
		is_entry=True,
	)


def create_exit_fill(
	raw_price: float,
	quantity: float,
	side: Side,
	config: BacktestConfig,
) -> Fill:
	"""Build an exit Fill with slippage and commission applied."""
	filled_price = apply_slippage_to_price(
		raw_price, side.value, is_entry=False, config=config
	)
	notional = filled_price * quantity
	comm = commission_cost(notional, config)
	slip_amt = abs(filled_price - raw_price) * quantity
	return Fill(
		price=filled_price,
		quantity=quantity,
		commission=comm,
		slippage_amount=slip_amt,
		side=side,
		is_entry=False,
	)


def check_stop_and_target(
	side: Side,
	stop_loss: Optional[float],
	take_profit: Optional[float],
	trailing_stop: Optional[float],
	bar_open: float,
	bar_high: float,
	bar_low: float,
	bar_close: float,
	config: BacktestConfig,
) -> ExitCheckResult:
	"""Resolve whether SL / TP / trailing was hit on this OHLC bar.

	Ambiguous candles (both SL and TP inside the bar) are handled
	according to config.ambiguous_bar_policy.

	Conservative policy (default):
	long  → assume SL first
	short → assume SL first
	"""
	# Effective stop: tighter of fixed SL and trailing
	effective_sl = stop_loss
	if trailing_stop is not None:
		if side == Side.LONG:
			effective_sl = (
				max(stop_loss, trailing_stop)
				if stop_loss is not None
				else trailing_stop
			)
		elif side == Side.SHORT:
			effective_sl = (
				min(stop_loss, trailing_stop)
				if stop_loss is not None
				else trailing_stop
			)

	sl_hit = False
	tp_hit = False

	if side == Side.LONG:
		if effective_sl is not None and bar_low <= effective_sl:
			sl_hit = True
		if take_profit is not None and bar_high >= take_profit:
			tp_hit = True
	elif side == Side.SHORT:
		if effective_sl is not None and bar_high >= effective_sl:
			sl_hit = True
		if take_profit is not None and bar_low <= take_profit:
			tp_hit = True

	if not sl_hit and not tp_hit:
		return ExitCheckResult(hit=False)

	# Ambiguous: both hit in same bar
	if sl_hit and tp_hit:
		policy = config.ambiguous_bar_policy
		if policy == AmbiguousBarPolicy.SKIP:
			return ExitCheckResult(hit=False)
		if policy == AmbiguousBarPolicy.OPTIMISTIC:
			# Favour the trader
			if side == Side.LONG:
				return ExitCheckResult(
					hit=True,
					reason=ExitReason.TAKE_PROFIT,
					fill_price=take_profit,
				)
			return ExitCheckResult(
				hit=True,
				reason=ExitReason.TAKE_PROFIT,
				fill_price=take_profit,
			)
		# CONSERVATIVE (default): SL first
		return ExitCheckResult(
			hit=True,
			reason=ExitReason.STOP_LOSS,
			fill_price=effective_sl,
		)

	if sl_hit:
		reason = (
			ExitReason.TRAILING_STOP
			if trailing_stop is not None
			and effective_sl == trailing_stop
			and (stop_loss is None or trailing_stop != stop_loss)
			else ExitReason.STOP_LOSS
		)
		return ExitCheckResult(hit=True, reason=reason, fill_price=effective_sl)

	# tp_hit only
	return ExitCheckResult(
		hit=True,
		reason=ExitReason.TAKE_PROFIT,
		fill_price=take_profit,
	)
