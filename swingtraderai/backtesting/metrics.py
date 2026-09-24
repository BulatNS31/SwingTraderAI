"""Performance metrics computed from trades + mark-to-market equity curve.

All risk-adjusted ratios use the equity curve (not just closed-trade PnL)
so open-position drawdowns are visible.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import List, Optional, Sequence

from swingtraderai.backtesting.models import (
	BacktestMetrics,
	EquityPoint,
	Trade,
)


def _period_years(start: datetime, end: datetime) -> float:
	"""Year fraction between two timestamps (min ~1 day to avoid div/0)."""
	delta = (end - start).total_seconds()
	years = delta / (365.25 * 24 * 3600)
	return max(years, 1.0 / 365.25)


def _equity_returns(equity_curve: Sequence[EquityPoint]) -> List[float]:
	"""Bar-to-bar simple returns of equity."""
	if len(equity_curve) < 2:
		return []
	rets: List[float] = []
	for i in range(1, len(equity_curve)):
		prev = equity_curve[i - 1].equity
		cur = equity_curve[i].equity
		if prev > 0:
			rets.append((cur - prev) / prev)
		else:
			rets.append(0.0)
	return rets


def _mean(xs: Sequence[float]) -> float:
	return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
	if len(xs) < 2:
		return 0.0
	m = _mean(xs)
	var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
	return math.sqrt(var)


def _downsample_annualization_factor(n_bars: int, years: float) -> float:
	"""Bars per year inferred from sample length."""
	if years <= 0 or n_bars <= 0:
		return 252.0
	return n_bars / years


def calculate_metrics(
	trades: List[Trade],
	equity_curve: List[EquityPoint],
	initial_capital: float,
	start: Optional[datetime] = None,
	end: Optional[datetime] = None,
) -> BacktestMetrics:
	"""Compute the full Phase-2 metric set."""
	m = BacktestMetrics()
	m.total_trades = len(trades)

	# --- Equity-based returns / drawdown ---
	if equity_curve:
		final_eq = equity_curve[-1].equity
		m.total_return = final_eq - initial_capital
		m.total_return_pct = (
			(m.total_return / initial_capital) * 100.0 if initial_capital else 0.0
		)
		m.max_drawdown = max((ep.drawdown for ep in equity_curve), default=0.0)
		m.max_drawdown_pct = max((ep.drawdown_pct for ep in equity_curve), default=0.0)

		eq_start = start or equity_curve[0].time
		eq_end = end or equity_curve[-1].time
		years = _period_years(eq_start, eq_end)

		if years > 0 and initial_capital > 0 and final_eq > 0:
			m.cagr = (final_eq / initial_capital) ** (1.0 / years) - 1.0
		else:
			m.cagr = None

		rets = _equity_returns(equity_curve)
		if rets:
			ann_factor = _downsample_annualization_factor(len(rets), years)
			mu = _mean(rets)
			sigma = _std(rets)
			if sigma > 1e-12:
				m.sharpe = (mu / sigma) * math.sqrt(ann_factor)
			else:
				m.sharpe = None

			downside = [r for r in rets if r < 0]
			down_sigma = _std(downside) if downside else 0.0
			if down_sigma > 1e-12:
				m.sortino = (mu / down_sigma) * math.sqrt(ann_factor)
			else:
				m.sortino = None

		if m.cagr is not None and m.max_drawdown_pct > 1e-12:
			m.calmar = m.cagr / m.max_drawdown_pct
		else:
			m.calmar = None

	if not trades:
		return m

	# --- Trade statistics (use net PnL after costs when available) ---
	net_pnls = [t.pnl - t.commission - t.slippage for t in trades]
	# Fallback: if costs are zero, net == gross
	pnls = net_pnls
	wins = [p for p in pnls if p > 0]
	losses = [p for p in pnls if p <= 0]

	m.winning_trades = len(wins)
	m.losing_trades = len(losses)
	m.win_rate = m.winning_trades / m.total_trades
	m.loss_rate = m.losing_trades / m.total_trades
	m.average_trade = _mean(pnls)
	m.average_win = _mean(wins) if wins else 0.0
	m.average_loss = _mean(losses) if losses else 0.0
	m.largest_win = max(pnls)
	m.largest_loss = min(pnls)
	m.average_bars_held = _mean([float(t.bars_held) for t in trades])
	m.avg_mfe = _mean([t.max_favorable_excursion for t in trades])
	m.avg_mae = _mean([t.max_adverse_excursion for t in trades])
	m.expectancy = m.average_trade

	gross_profit = sum(wins) if wins else 0.0
	gross_loss = abs(sum(losses)) if losses else 0.0
	if gross_loss > 1e-12:
		m.profit_factor = gross_profit / gross_loss
	elif gross_profit > 0:
		m.profit_factor = None  # infinite — leave as None
	else:
		m.profit_factor = 0.0

	return m
