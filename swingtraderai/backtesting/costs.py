"""Помощники по транзакционным издержкам.

Комиссия и проскальзывание применяются как при входе, так и при выходе из сделки.
Все функции возвращают абсолютные суммы в денежном выражении
(положительное значение = стоимость).
"""

from __future__ import annotations

from .config import BacktestConfig


def commission_cost(notional: float, config: BacktestConfig) -> float:
	"""Absolute commission for a fill of given notional value."""
	pct_part = abs(notional) * config.commission_pct
	return pct_part + config.fixed_commission


def slippage_cost(notional: float, config: BacktestConfig) -> float:
	"""Absolute slippage cost (adverse price movement)."""
	return abs(notional) * config.slippage_pct


def apply_slippage_to_price(
	price: float,
	side: str,
	is_entry: bool,
	config: BacktestConfig,
) -> float:
	"""Adjust fill price for slippage.

	Long entry / short exit → price increases (worse)
	Short entry / long exit → price decreases (worse)
	"""
	slip = config.slippage_pct
	if side == "long":
		if is_entry:
			return price * (1.0 + slip)
		return price * (1.0 - slip)
	if side == "short":
		if is_entry:
			return price * (1.0 - slip)
		return price * (1.0 + slip)
	return price


def total_roundtrip_cost(
	entry_notional: float, exit_notional: float, config: BacktestConfig
) -> float:
	"""Sum of commission + slippage on both legs."""
	return (
		commission_cost(entry_notional, config)
		+ commission_cost(exit_notional, config)
		+ slippage_cost(entry_notional, config)
		+ slippage_cost(exit_notional, config)
	)
