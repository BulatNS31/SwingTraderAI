"""Position lifecycle: open, update, close.

Phase 1 constraints:
  - single position
  - long only (short gated by config.allow_short)
  - next-open entry is handled by the engine (pending order)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from swingtraderai.backtesting.models import (
	ExitReason,
	Position,
	Side,
	Signal,
	Trade,
)

from .config import (
	BacktestConfig,
	PositionSizingMode,
)
from .costs import commission_cost, slippage_cost
from .execution import (
	Fill,
	check_stop_and_target,
	create_entry_fill,
	create_exit_fill,
)


class PositionManager:
	def __init__(self, config: BacktestConfig) -> None:
		self.config = config
		self.cash: float = config.initial_capital
		self.equity: float = config.initial_capital
		self.peak_equity: float = config.initial_capital
		self.position: Optional[Position] = None
		self.pending_entry: Optional[Signal] = None  # filled on next open
		self.closed_trades: List[Trade] = []

	# ------------------------------------------------------------------
	# Sizing
	# ------------------------------------------------------------------

	def _compute_quantity(
		self, entry_price: float, stop_loss: Optional[float], side: Side
	) -> float:
		cfg = self.config
		if entry_price <= 0:
			return 0.0

		if cfg.position_sizing_mode == PositionSizingMode.FIXED_QUANTITY:
			qty = cfg.position_size
		elif cfg.position_sizing_mode == PositionSizingMode.FIXED_PERCENT_EQUITY:
			notional = self.equity * cfg.position_size
			qty = notional / entry_price
		elif cfg.position_sizing_mode == PositionSizingMode.RISK_BASED:
			if stop_loss is None or abs(entry_price - stop_loss) < 1e-12:
				# fallback to percent equity
				notional = self.equity * cfg.risk_per_trade
				qty = notional / entry_price
			else:
				risk_amount = self.equity * cfg.risk_per_trade
				risk_per_unit = abs(entry_price - stop_loss)
				qty = risk_amount / risk_per_unit
		else:
			qty = 0.0

		# Caps
		max_notional = self.equity * cfg.max_position_pct
		if qty * entry_price > max_notional:
			qty = max_notional / entry_price

		# Sufficient capital (including estimated costs)
		cost_buffer = 1.0 + cfg.commission_pct + cfg.slippage_pct
		if qty * entry_price * cost_buffer > self.cash:
			qty = self.cash / (entry_price * cost_buffer)

		return max(0.0, qty)

	# ------------------------------------------------------------------
	# Entry
	# ------------------------------------------------------------------

	def queue_entry(self, signal: Signal) -> None:
		"""Queue a signal to be filled on the next bar's open."""
		if self.position is not None:
			return
		if self.pending_entry is not None:
			return
		if signal.side == Side.NEUTRAL:
			return
		if signal.side == Side.SHORT and not self.config.allow_short:
			return
		if signal.signal_score < self.config.signal_threshold:
			return
		self.pending_entry = signal

	def try_fill_pending_entry(
		self, bar_open: float, bar_time: datetime, bar_index: int
	) -> Optional[Fill]:
		"""Execute pending entry on this bar's open."""
		if self.pending_entry is None or self.position is not None:
			self.pending_entry = None
			return None

		signal = self.pending_entry
		self.pending_entry = None

		qty = self._compute_quantity(bar_open, signal.stop_loss, signal.side)
		if qty <= 0:
			return None

		fill = create_entry_fill(bar_open, qty, signal.side, self.config)
		cost = fill.price * fill.quantity + fill.commission
		if cost > self.cash:
			return None

		self.cash -= cost
		self.position = Position(
			side=signal.side,
			quantity=fill.quantity,
			entry_price=fill.price,
			entry_time=bar_time,
			entry_bar_index=bar_index,
			stop_loss=signal.stop_loss,
			take_profit=signal.take_profit,
			max_favorable_price=fill.price,
			max_adverse_price=fill.price,
			signal=signal,
			bars_held=0,
			trailing_stop=None,
		)
		return fill

	# ------------------------------------------------------------------
	# Intrabar management
	# ------------------------------------------------------------------

	def update_on_bar(
		self,
		bar_open: float,
		bar_high: float,
		bar_low: float,
		bar_close: float,
		bar_time: datetime,
		signal: Optional[Signal] = None,
	) -> Optional[Trade]:
		"""Update open position: excursions, trailing, SL/TP, time exit.

		Returns a closed Trade if an exit occurred, else None.
		"""
		if self.position is None:
			return None

		pos = self.position
		pos.bars_held += 1
		pos.update_excursions(bar_high, bar_low)

		# Trailing stop update
		if self.config.trailing_stop:
			self._update_trailing(pos, bar_high, bar_low)

		# SL / TP check
		exit_check = check_stop_and_target(
			side=pos.side,
			stop_loss=pos.stop_loss,
			take_profit=pos.take_profit,
			trailing_stop=pos.trailing_stop,
			bar_open=bar_open,
			bar_high=bar_high,
			bar_low=bar_low,
			bar_close=bar_close,
			config=self.config,
		)
		if exit_check.hit and exit_check.fill_price is not None:
			return self._close(
				exit_check.fill_price,
				bar_time,
				exit_check.reason or ExitReason.STOP_LOSS,
			)

		# Time-based exit
		if (
			self.config.max_bars_in_trade is not None
			and pos.bars_held >= self.config.max_bars_in_trade
		):
			return self._close(bar_close, bar_time, ExitReason.TIME_EXIT)

		# Signal reverse exit (optional)
		if signal is not None and signal.side != Side.NEUTRAL:
			if pos.side == Side.LONG and signal.side == Side.SHORT:
				return self._close(bar_close, bar_time, ExitReason.SIGNAL_REVERSE)
			if pos.side == Side.SHORT and signal.side == Side.LONG:
				return self._close(bar_close, bar_time, ExitReason.SIGNAL_REVERSE)

		return None

	def _update_trailing(self, pos: Position, high: float, low: float) -> None:
		cfg = self.config
		if cfg.trailing_stop_pct is not None:
			if pos.side == Side.LONG:
				candidate = high * (1.0 - cfg.trailing_stop_pct)
				if pos.trailing_stop is None or candidate > pos.trailing_stop:
					pos.trailing_stop = candidate
			elif pos.side == Side.SHORT:
				candidate = low * (1.0 + cfg.trailing_stop_pct)
				if pos.trailing_stop is None or candidate < pos.trailing_stop:
					pos.trailing_stop = candidate

	# ------------------------------------------------------------------
	# Close helpers
	# ------------------------------------------------------------------

	def _close(
		self, raw_exit_price: float, exit_time: datetime, reason: ExitReason
	) -> Trade:
		assert self.position is not None
		pos = self.position
		fill = create_exit_fill(raw_exit_price, pos.quantity, pos.side, self.config)

		# Cash proceeds
		if pos.side == Side.LONG:
			proceeds = fill.price * fill.quantity - fill.commission
			self.cash += proceeds
			raw_pnl = (fill.price - pos.entry_price) * pos.quantity
		else:
			# Short: we received cash at entry; now buy back
			proceeds = pos.entry_price * pos.quantity  # already added at entry logic
			# For simplicity in Phase 1 we treat short PnL symmetrically
			raw_pnl = (pos.entry_price - fill.price) * pos.quantity
			self.cash += raw_pnl - fill.commission

		# total_commission = (
		# 	fill.commission
		# )  # entry commission already deducted from cash
		# Re-compute entry commission for reporting
		entry_notional = pos.entry_price * pos.quantity

		entry_comm = commission_cost(entry_notional, self.config)
		total_comm = entry_comm + fill.commission
		total_slip = slippage_cost(entry_notional, self.config) + fill.slippage_amount

		# net_pnl = raw_pnl - total_comm - (total_slip - fill.slippage_amount)
		# Simpler accounting: pnl is price PnL, costs separate
		pnl = raw_pnl
		pnl_pct = (
			(fill.price / pos.entry_price - 1.0)
			if pos.side == Side.LONG
			else (pos.entry_price / fill.price - 1.0)
		)
		if pos.side == Side.SHORT:
			pnl_pct = (pos.entry_price - fill.price) / pos.entry_price

		# MFE / MAE in price units
		if pos.side == Side.LONG:
			mfe = pos.max_favorable_price - pos.entry_price
			mae = pos.entry_price - pos.max_adverse_price
		else:
			mfe = pos.entry_price - pos.max_favorable_price
			mae = pos.max_adverse_price - pos.entry_price

		trade = Trade(
			signal_timestamp=pos.signal.timestamp,
			ticker=pos.signal.ticker,
			timeframe=pos.signal.timeframe,
			side=pos.side,
			entry_price=pos.entry_price,
			entry_time=pos.entry_time,
			exit_price=fill.price,
			exit_time=exit_time,
			stop_loss=pos.stop_loss,
			take_profit=pos.take_profit,
			position_size=pos.quantity,
			pnl=pnl,
			pnl_percent=pnl_pct * 100.0,
			commission=total_comm,
			slippage=total_slip,
			exit_reason=reason,
			bars_held=pos.bars_held,
			max_favorable_excursion=mfe,
			max_adverse_excursion=mae,
			mfe_percent=(mfe / pos.entry_price) * 100.0 if pos.entry_price else 0.0,
			mae_percent=(mae / pos.entry_price) * 100.0 if pos.entry_price else 0.0,
			signal_score=pos.signal.signal_score,
			market_regime=pos.signal.market_regime,
			signal_type=pos.signal.signal_type,
			ml_probability=pos.signal.ml_probability,
		)
		self.closed_trades.append(trade)
		self.position = None
		return trade

	def close_all(self, bar_close: float, bar_time: datetime) -> List[Trade]:
		"""Force-close remaining position at end of data."""
		if self.position is None:
			return []
		trade = self._close(bar_close, bar_time, ExitReason.END_OF_DATA)
		return [trade]

	def mark_to_market(self, current_price: float) -> float:
		"""Update equity including unrealized PnL."""
		unrealized = 0.0
		if self.position is not None:
			unrealized = self.position.unrealized_pnl(current_price)
		self.equity = self.cash + unrealized
		if self.equity > self.peak_equity:
			self.peak_equity = self.equity
		return self.equity

	@property
	def current_drawdown(self) -> float:
		if self.peak_equity <= 0:
			return 0.0
		return self.peak_equity - self.equity

	@property
	def current_drawdown_pct(self) -> float:
		if self.peak_equity <= 0:
			return 0.0
		return (self.peak_equity - self.equity) / self.peak_equity
