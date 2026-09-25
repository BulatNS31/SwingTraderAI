"""ML-augmented signal generation for Mode B backtests.

Combines the deterministic composite signal with a FrozenModel probability.
The ML model is never re-fit during the backtest window.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from swingtraderai.backtesting.config import BacktestConfig
from swingtraderai.backtesting.ml_features import last_feature_row
from swingtraderai.backtesting.ml_model import FrozenModel
from swingtraderai.backtesting.models import Side, Signal
from swingtraderai.backtesting.signal_generator import (
	SignalGenerator,
	_default_sl_tp,
	_simple_atr,
)


class MLSignalGenerator:
	"""Composite signal filtered / confirmed by a frozen ML model.

	Policy (configurable via constructor):
	- ``require_agreement=True`` (default): act only when composite side
	and ML side agree (or composite is neutral and ML is strong).
	- ``require_agreement=False``: ML side overrides composite when ML
	is not neutral; otherwise fall back to composite.
	"""

	def __init__(
		self,
		config: BacktestConfig,
		frozen_model: FrozenModel,
		require_agreement: bool = True,
		ml_only: bool = False,
	) -> None:
		self.config = config
		self.frozen_model = frozen_model
		self.require_agreement = require_agreement
		self.ml_only = ml_only
		self._composite = SignalGenerator(config.model_copy(update={"use_ml": False}))

	def generate(
		self,
		history: pd.DataFrame,
		ticker: str,
		timeframe: str,
		bar_timestamp: datetime,
	) -> Signal:
		hist = history.copy()
		hist.columns = [c.lower() for c in hist.columns]
		close = float(hist["close"].iloc[-1]) if len(hist) else 0.0

		# Guard: do not use model before its training end (no in-sample by default)
		# Caller may still run in-sample deliberately; we only annotate metadata.
		in_sample = False
		if hist["time"].notna().any() if "time" in hist.columns else False:
			pass
		if bar_timestamp <= self.frozen_model.train_end:
			in_sample = True

		row = last_feature_row(hist, self.frozen_model.feature_columns)
		ml_prob: Optional[float] = None
		ml_side = Side.NEUTRAL
		if row is not None:
			ml_prob = self.frozen_model.predict_proba_long(row)
			decided = self.frozen_model.decide_side(ml_prob)
			if decided == "long":
				ml_side = Side.LONG
			elif decided == "short":
				ml_side = Side.SHORT
				if not self.config.allow_short:
					ml_side = Side.NEUTRAL

		if self.ml_only:
			side = ml_side
			signal_type = {
				Side.LONG: "BUY",
				Side.SHORT: "SELL",
				Side.NEUTRAL: "NEUTRAL",
			}[side]
			score = float(min(10.0, max(1.0, abs((ml_prob or 0.5) - 0.5) * 20)))
			atr = _simple_atr(hist)
			sl, tp = _default_sl_tp(close, side, self.config, atr=atr)
			return Signal(
				timestamp=bar_timestamp,
				ticker=ticker,
				timeframe=timeframe,
				side=side,
				signal_type=signal_type,
				signal_score=score,
				confidence=ml_prob,
				entry_reference_price=close,
				stop_loss=sl,
				take_profit=tp,
				ml_probability=ml_prob,
				market_regime="ml_only",
				metadata={
					"model_version": self.frozen_model.model_version,
					"in_sample": in_sample,
				},
			)

		base = self._composite.generate(history, ticker, timeframe, bar_timestamp)

		if ml_prob is None:
			# Features not warm — pure composite
			base.ml_probability = None
			base.metadata = {
				**(base.metadata or {}),
				"model_version": self.frozen_model.model_version,
				"in_sample": in_sample,
				"ml_status": "cold",
			}
			return base

		if self.require_agreement:
			if base.side == Side.NEUTRAL:
				side = Side.NEUTRAL
				signal_type = "NEUTRAL"
				score = 1.0
			elif base.side == ml_side:
				side = base.side
				signal_type = base.signal_type
				score = min(10.0, base.signal_score + 1.0)
			else:
				side = Side.NEUTRAL
				signal_type = "NEUTRAL"
				score = 1.0
		else:
			if ml_side != Side.NEUTRAL:
				side = ml_side
				signal_type = "BUY" if side == Side.LONG else "SELL"
				score = base.signal_score
			else:
				side = base.side
				signal_type = base.signal_type
				score = base.signal_score

		atr = _simple_atr(hist)
		sl, tp = _default_sl_tp(close, side, self.config, atr=atr)

		return Signal(
			timestamp=bar_timestamp,
			ticker=ticker,
			timeframe=timeframe,
			side=side,
			signal_type=signal_type,
			signal_score=score,
			confidence=ml_prob,
			entry_reference_price=close,
			stop_loss=sl if side != Side.NEUTRAL else None,
			take_profit=tp if side != Side.NEUTRAL else None,
			ml_probability=ml_prob,
			market_regime=base.market_regime,
			indicators_used=list(base.indicators_used),
			metadata={
				"model_version": self.frozen_model.model_version,
				"in_sample": in_sample,
				"composite_side": base.side.value,
				"ml_side": ml_side.value,
				"require_agreement": self.require_agreement,
			},
		)
