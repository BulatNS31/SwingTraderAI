"""Backtest configuration.

Здесь указаны все параметры исполнения, определения размера и рисков.
Значения по умолчанию соответствуют требованиям проекта:
- entry_mode = next_open
- ambiguous_bar_policy = conservative
- long-only MVP
"""

from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EntryMode(StrEnum):
	"""When a signal generated on bar T is filled."""

	NEXT_OPEN = "next_open"  # signal on close T → fill on open T+1 (default)
	CURRENT_CLOSE = "current_close"  # explicit opt-in only


class AmbiguousBarPolicy(StrEnum):
	"""How to resolve SL and TP both touched in the same OHLC bar."""

	CONSERVATIVE = "conservative"  # assume SL first (default)
	OPTIMISTIC = "optimistic"  # assume TP first
	SKIP = "skip"  # leave position open, resolve later


class PositionSizingMode(StrEnum):
	FIXED_QUANTITY = "fixed_quantity"
	FIXED_PERCENT_EQUITY = "fixed_percent_equity"
	RISK_BASED = "risk_based"


class StopLossMode(StrEnum):
	FIXED_PCT = "fixed_pct"
	ATR_MULTIPLE = "atr_multiple"
	SIGNAL = "signal"  # use stop from Signal if provided


class TakeProfitMode(StrEnum):
	FIXED_PCT = "fixed_pct"
	ATR_MULTIPLE = "atr_multiple"
	SIGNAL = "signal"
	RR_RATIO = "rr_ratio"  # risk-reward multiple of SL distance


class BacktestConfig(BaseModel):
	"""Full configuration for a single-ticker backtest run."""

	# Capital
	initial_capital: float = Field(100_000.0, gt=0)

	# Data / warmup
	warmup_bars: int = Field(50, ge=0)

	# Execution
	entry_mode: EntryMode = EntryMode.NEXT_OPEN
	ambiguous_bar_policy: AmbiguousBarPolicy = AmbiguousBarPolicy.CONSERVATIVE
	allow_short: bool = False  # Phase 1: long only

	# Costs (applied on both entry and exit)
	commission_pct: float = Field(0.0005, ge=0)  # 0.05% per side
	slippage_pct: float = Field(0.0005, ge=0)  # 0.05% per side
	fixed_commission: float = Field(0.0, ge=0)

	# Position sizing
	position_sizing_mode: PositionSizingMode = PositionSizingMode.FIXED_PERCENT_EQUITY
	position_size: float = Field(1.0, gt=0)  # quantity or % of equity depending on mode
	risk_per_trade: float = Field(0.01, gt=0, le=1.0)  # for risk_based
	max_position_pct: float = Field(0.25, gt=0, le=1.0)
	max_positions: int = Field(1, ge=1)

	# Stops / targets
	stop_loss_mode: StopLossMode = StopLossMode.FIXED_PCT
	stop_loss_pct: float = Field(0.02, gt=0)  # 2%
	stop_loss_atr_mult: float = Field(1.5, gt=0)
	take_profit_mode: TakeProfitMode = TakeProfitMode.RR_RATIO
	take_profit_pct: float = Field(0.04, gt=0)
	take_profit_atr_mult: float = Field(3.0, gt=0)
	risk_reward_ratio: float = Field(2.0, gt=0)

	trailing_stop: bool = False
	trailing_stop_pct: Optional[float] = Field(None, gt=0)
	trailing_stop_atr_mult: Optional[float] = Field(None, gt=0)

	max_bars_in_trade: Optional[int] = Field(None, ge=1)

	# Signal filters
	use_ml: bool = False
	signal_threshold: int = Field(5, ge=1, le=10)  # min strength to act
	signal_types_long: tuple[str, ...] = ("BUY", "STRONG_BUY")
	signal_types_short: tuple[str, ...] = ("SELL", "STRONG_SELL")

	# Metadata
	model_version: Optional[str] = None
	notes: Optional[str] = None

	model_config = {"extra": "forbid"}

	@field_validator("position_size")
	@classmethod
	def _position_size_positive(cls, v: float) -> float:
		if v <= 0:
			raise ValueError("position_size must be > 0")
		return v

	@model_validator(mode="after")
	def _trailing_consistency(self) -> "BacktestConfig":
		if self.trailing_stop:
			if self.trailing_stop_pct is None and self.trailing_stop_atr_mult is None:
				raise ValueError(
					"trailing_stop=True requires "
					"trailing_stop_pct or trailing_stop_atr_mult"
				)
		return self

	def is_long_signal(self, signal_type: str) -> bool:
		return signal_type in self.signal_types_long

	def is_short_signal(self, signal_type: str) -> bool:
		return signal_type in self.signal_types_short
