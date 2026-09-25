"""Walk-forward ML validation.

Each fold:
1. Train FrozenModel on [train_start, train_end]  (scaler fit only here)
2. Backtest on (train_end, test_end] with that frozen model
3. Roll forward

Folds never mix train and test rows for fitting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from swingtraderai.backtesting.config import BacktestConfig
from swingtraderai.backtesting.engine import BacktestEngine
from swingtraderai.backtesting.ml_model import FrozenModel, train_frozen_model
from swingtraderai.backtesting.ml_signal import MLSignalGenerator
from swingtraderai.backtesting.models import BacktestResult


@dataclass
class WalkForwardFold:
	fold_id: int
	train_start: datetime
	train_end: datetime
	test_start: datetime
	test_end: datetime
	model_version: str
	result: Optional[BacktestResult] = None
	error: Optional[str] = None
	n_train_rows: int = 0


@dataclass
class WalkForwardResult:
	folds: List[WalkForwardFold] = field(default_factory=list)
	config: Optional[BacktestConfig] = None
	ticker: str = ""
	timeframe: str = ""

	@property
	def successful_folds(self) -> List[WalkForwardFold]:
		return [f for f in self.folds if f.result is not None]

	def summary_metrics(self) -> Dict[str, Any]:
		"""Aggregate simple stats across successful folds."""
		ok = self.successful_folds
		if not ok:
			return {"n_folds": 0}
		returns = [f.result.metrics.total_return_pct for f in ok if f.result]
		trades = [f.result.metrics.total_trades for f in ok if f.result]
		return {
			"n_folds": len(ok),
			"n_failed": len(self.folds) - len(ok),
			"avg_return_pct": sum(returns) / len(returns) if returns else 0.0,
			"total_trades": sum(trades),
			"fold_returns_pct": returns,
		}


def generate_expanding_folds(
	df: pd.DataFrame,
	train_bars: int,
	test_bars: int,
	step_bars: Optional[int] = None,
	min_date: Optional[pd.Timestamp] = None,
	max_date: Optional[pd.Timestamp] = None,
) -> List[Dict[str, pd.Timestamp]]:
	"""Expanding-window folds on a bar index basis.

	Fold k:
	train = rows [0, train_bars + k*step)
	test  = rows [train_end, train_end + test_bars)
	"""
	data = df.copy()
	data.columns = [c.lower() for c in data.columns]
	data["time"] = pd.to_datetime(data["time"])
	data = data.sort_values("time").reset_index(drop=True)
	if min_date is not None:
		data = data[data["time"] >= pd.Timestamp(min_date)]
	if max_date is not None:
		data = data[data["time"] <= pd.Timestamp(max_date)]
	data = data.reset_index(drop=True)

	step = step_bars if step_bars is not None else test_bars
	folds: List[Dict[str, pd.Timestamp]] = []
	n = len(data)
	train_end_idx = train_bars
	fold_id = 0
	while train_end_idx + test_bars <= n:
		train_start_idx = 0  # expanding
		test_end_idx = train_end_idx + test_bars
		folds.append(
			{
				"fold_id": fold_id,
				"train_start": data.loc[train_start_idx, "time"],
				"train_end": data.loc[train_end_idx - 1, "time"],
				"test_start": data.loc[train_end_idx, "time"],
				"test_end": data.loc[test_end_idx - 1, "time"],
			}
		)
		fold_id += 1
		train_end_idx += step
	return folds


def generate_rolling_folds(
	df: pd.DataFrame,
	train_bars: int,
	test_bars: int,
	step_bars: Optional[int] = None,
) -> List[Dict[str, pd.Timestamp]]:
	"""Fixed-size rolling train window."""
	data = df.copy()
	data.columns = [c.lower() for c in data.columns]
	data["time"] = pd.to_datetime(data["time"])
	data = data.sort_values("time").reset_index(drop=True)

	step = step_bars if step_bars is not None else test_bars
	folds: List[Dict[str, pd.Timestamp]] = []
	n = len(data)
	start = 0
	fold_id = 0
	while start + train_bars + test_bars <= n:
		train_end_idx = start + train_bars
		test_end_idx = train_end_idx + test_bars
		folds.append(
			{
				"fold_id": fold_id,
				"train_start": data.loc[start, "time"],
				"train_end": data.loc[train_end_idx - 1, "time"],
				"test_start": data.loc[train_end_idx, "time"],
				"test_end": data.loc[test_end_idx - 1, "time"],
			}
		)
		fold_id += 1
		start += step
	return folds


def run_walk_forward(
	df: pd.DataFrame,
	config: BacktestConfig,
	ticker: str = "UNKNOWN",
	timeframe: str = "1h",
	train_bars: int = 200,
	test_bars: int = 50,
	step_bars: Optional[int] = None,
	mode: str = "expanding",  # or "rolling"
	require_agreement: bool = True,
	ml_only: bool = False,
	horizon: int = 5,
	min_train_rows: int = 30,
	model_params: Optional[Dict[str, Any]] = None,
) -> WalkForwardResult:
	"""Execute full walk-forward loop."""
	if mode == "rolling":
		fold_specs = generate_rolling_folds(df, train_bars, test_bars, step_bars)
	else:
		fold_specs = generate_expanding_folds(df, train_bars, test_bars, step_bars)

	wf = WalkForwardResult(config=config, ticker=ticker, timeframe=timeframe)

	for spec in fold_specs:
		fold = WalkForwardFold(
			fold_id=int(spec["fold_id"]),
			train_start=pd.Timestamp(spec["train_start"]).to_pydatetime(),
			train_end=pd.Timestamp(spec["train_end"]).to_pydatetime(),
			test_start=pd.Timestamp(spec["test_start"]).to_pydatetime(),
			test_end=pd.Timestamp(spec["test_end"]).to_pydatetime(),
			model_version=f"wf-fold{spec['fold_id']}",
		)
		try:
			frozen = train_frozen_model(
				df,
				train_start=fold.train_start,
				train_end=fold.train_end,
				horizon=horizon,
				model_version=fold.model_version,
				min_rows=min_train_rows,
				model_params=model_params,
			)
			fold.n_train_rows = int(frozen.metadata.get("n_train_rows", 0))

			gen = MLSignalGenerator(
				config=config,
				frozen_model=frozen,
				require_agreement=require_agreement,
				ml_only=ml_only,
			)
			# Keep full history for features; only *trade* on the test window.
			engine = BacktestEngine(config, signal_generator=gen)
			result = engine.run(
				df,
				ticker=ticker,
				timeframe=timeframe,
				trade_start=pd.Timestamp(fold.test_start),
				trade_end=pd.Timestamp(fold.test_end),
			)
			result.model_version = fold.model_version
			result.metadata = {
				**(result.metadata or {}),
				"fold_id": fold.fold_id,
				"train_start": str(fold.train_start),
				"train_end": str(fold.train_end),
				"test_start": str(fold.test_start),
				"test_end": str(fold.test_end),
			}
			fold.result = result
		except Exception as exc:
			fold.error = str(exc)
		wf.folds.append(fold)

	return wf


def run_frozen_backtest(
	df: pd.DataFrame,
	config: BacktestConfig,
	frozen_model: FrozenModel,
	ticker: str = "UNKNOWN",
	timeframe: str = "1h",
	test_start: Optional[pd.Timestamp] = None,
	test_end: Optional[pd.Timestamp] = None,
	require_agreement: bool = True,
	ml_only: bool = False,
	forbid_in_sample: bool = True,
) -> BacktestResult:
	"""Single frozen-model backtest on an explicit test window.

	If ``forbid_in_sample`` is True (default), test_start must be strictly
	after frozen_model.train_end.
	"""
	if test_start is None:
		test_start = pd.Timestamp(frozen_model.train_end) + pd.Timedelta(seconds=1)
	if forbid_in_sample and pd.Timestamp(test_start) <= pd.Timestamp(
		frozen_model.train_end
	):
		raise ValueError(
			f"test_start ({test_start}) must be after train_end "
			f"({frozen_model.train_end}) when forbid_in_sample=True"
		)

	gen = MLSignalGenerator(
		config=config,
		frozen_model=frozen_model,
		require_agreement=require_agreement,
		ml_only=ml_only,
	)
	engine = BacktestEngine(config, signal_generator=gen)
	result = engine.run(
		df,
		ticker=ticker,
		timeframe=timeframe,
		trade_start=test_start,
		trade_end=test_end,
	)
	result.model_version = frozen_model.model_version
	result.metadata = {
		**(result.metadata or {}),
		"train_start": str(frozen_model.train_start),
		"train_end": str(frozen_model.train_end),
		"forbid_in_sample": forbid_in_sample,
	}
	return result
