"""Frozen ML model artifact for backtesting.

A FrozenModel is trained on an explicit [train_start, train_end] window and
must never be re-fit on test data during a frozen-model backtest.

Walk-forward creates a *new* FrozenModel per fold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from swingtraderai.backtesting.ml_features import (
	DEFAULT_FEATURE_COLUMNS,
	build_feature_frame,
	make_labels,
)


@dataclass
class FrozenModel:
	"""Immutable inference bundle."""

	model: Any  # sklearn / xgboost classifier with predict_proba
	scaler: Any  # fitted StandardScaler (or None)
	feature_columns: List[str]
	train_start: datetime
	train_end: datetime
	model_version: str
	long_threshold: float = 0.55
	short_threshold: float = 0.45
	metadata: Dict[str, Any] = field(default_factory=dict)

	def predict_proba_long(self, feature_row: pd.Series) -> float:
		"""P(long) for a single feature row (already point-in-time)."""
		x = feature_row[self.feature_columns].astype(float).values.reshape(1, -1)
		if self.scaler is not None:
			x = self.scaler.transform(x)
		proba = self.model.predict_proba(x)[0]
		# binary: class 1 = long
		if len(proba) > 1:
			return float(proba[1])
		return float(proba[0])

	def decide_side(self, probability: float) -> str:
		if probability >= self.long_threshold:
			return "long"
		if probability <= self.short_threshold:
			return "short"
		return "neutral"


def _try_xgb_classifier(**kwargs: Any) -> Any:
	try:
		from xgboost import XGBClassifier

		defaults = {
			"n_estimators": 50,
			"max_depth": 3,
			"learning_rate": 0.1,
			"subsample": 0.9,
			"colsample_bytree": 0.9,
			"eval_metric": "logloss",
			"verbosity": 0,
		}
		defaults.update(kwargs)
		return XGBClassifier(**defaults)
	except Exception:
		from sklearn.ensemble import GradientBoostingClassifier

		return GradientBoostingClassifier(
			n_estimators=kwargs.get("n_estimators", 50),
			max_depth=kwargs.get("max_depth", 3),
			learning_rate=kwargs.get("learning_rate", 0.1),
		)


def train_frozen_model(
	df: pd.DataFrame,
	train_start: datetime | pd.Timestamp,
	train_end: datetime | pd.Timestamp,
	feature_columns: Optional[List[str]] = None,
	horizon: int = 5,
	label_threshold: float = 0.0,
	model_version: str = "v1",
	long_threshold: float = 0.55,
	short_threshold: float = 0.45,
	min_rows: int = 30,
	model_params: Optional[Dict[str, Any]] = None,
) -> FrozenModel:
	"""Fit model + scaler strictly on rows within [train_start, train_end].

	Labels use future returns *within the training window only*.
	Rows whose forward horizon would cross train_end are dropped.
	"""
	from sklearn.preprocessing import StandardScaler

	cols = feature_columns or list(DEFAULT_FEATURE_COLUMNS)
	data = df.copy()
	data.columns = [c.lower() for c in data.columns]
	data["time"] = pd.to_datetime(data["time"])
	data = data.sort_values("time").reset_index(drop=True)

	ts = pd.Timestamp(train_start)
	te = pd.Timestamp(train_end)
	mask = (data["time"] >= ts) & (data["time"] <= te)
	train_df = data.loc[mask].reset_index(drop=True)
	if len(train_df) < min_rows:
		raise ValueError(
			f"Train window too small: {len(train_df)} rows "
			f"(need ≥ {min_rows}) in [{ts}, {te}]"
		)

	feats = build_feature_frame(train_df)
	labels = make_labels(train_df, horizon=horizon, threshold=label_threshold)

	# Drop rows with NaN features or labels (label NaN includes horizon tail)
	frame = feats[cols].copy()
	frame["__y"] = labels
	frame = frame.dropna()
	if len(frame) < min_rows:
		raise ValueError(
			f"After dropna only {len(frame)} train rows (need ≥ {min_rows})"
		)

	X = frame[cols].values
	y = frame["__y"].astype(int).values

	scaler = StandardScaler()
	X_scaled = scaler.fit_transform(X)  # fit ONLY on train

	clf = _try_xgb_classifier(**(model_params or {}))
	clf.fit(X_scaled, y)

	return FrozenModel(
		model=clf,
		scaler=scaler,
		feature_columns=cols,
		train_start=ts.to_pydatetime(),
		train_end=te.to_pydatetime(),
		model_version=model_version,
		long_threshold=long_threshold,
		short_threshold=short_threshold,
		metadata={
			"horizon": horizon,
			"label_threshold": label_threshold,
			"n_train_rows": int(len(frame)),
			"positive_rate": float(y.mean()),
		},
	)


def save_frozen_model(model: FrozenModel, path: str | Path) -> Path:
	import joblib

	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	joblib.dump(
		{
			"model": model.model,
			"scaler": model.scaler,
			"feature_columns": model.feature_columns,
			"train_start": model.train_start,
			"train_end": model.train_end,
			"model_version": model.model_version,
			"long_threshold": model.long_threshold,
			"short_threshold": model.short_threshold,
			"metadata": model.metadata,
		},
		path,
	)
	return path


def load_frozen_model(
	path: str | Path,
	*,
	train_start: Optional[datetime] = None,
	train_end: Optional[datetime] = None,
	model_version: Optional[str] = None,
	long_threshold: float = 0.55,
	short_threshold: float = 0.45,
) -> FrozenModel:
	"""Load a frozen artifact.

	Compatible with:
	- backtesting save_frozen_model format
	- project trainer/loader format:
		{model, scaler, features, ticker_id, timeframe, metrics, ...}
	"""
	import joblib

	blob = joblib.load(path)
	if "model" not in blob or "scaler" not in blob:
		raise KeyError(
			f"Artifact {path} must contain 'model' and 'scaler' keys, "
			f"got {sorted(blob.keys())}"
		)

	# Project uses "features"; our format uses "feature_columns"
	feature_columns = list(
		blob.get("feature_columns") or blob.get("features") or DEFAULT_FEATURE_COLUMNS
	)

	ts = blob.get("train_start", train_start)
	te = blob.get("train_end", train_end)
	if ts is None:
		ts = datetime(1970, 1, 1)
	if te is None:
		te = datetime(1970, 1, 1)
	if isinstance(ts, str):
		ts = pd.Timestamp(ts).to_pydatetime()
	if isinstance(te, str):
		te = pd.Timestamp(te).to_pydatetime()

	version = model_version or blob.get("model_version") or Path(path).stem
	meta = dict(blob.get("metadata") or {})
	for k in ("ticker_id", "timeframe", "strategy", "horizon", "metrics"):
		if k in blob and k not in meta:
			meta[k] = blob[k]
	meta["source_path"] = str(path)

	return FrozenModel(
		model=blob["model"],
		scaler=blob["scaler"],
		feature_columns=feature_columns,
		train_start=ts,
		train_end=te,
		model_version=str(version),
		long_threshold=float(blob.get("long_threshold", long_threshold)),
		short_threshold=float(blob.get("short_threshold", short_threshold)),
		metadata=meta,
	)


def frozen_model_from_project_artifact(
	path: str | Path,
	train_end: datetime,
	train_start: Optional[datetime] = None,
	model_version: Optional[str] = None,
	long_threshold: float = 0.65,
	short_threshold: float = 0.35,
) -> FrozenModel:
	"""Wrap a live SwingTraderAI joblib artifact for backtesting.

	Project defaults (MARKET_DATA_SCHEMA): LONG_THRESHOLD=0.65, SHORT_THRESHOLD=0.35.
	``train_end`` must be supplied by the caller — the live artifact may not
	record the training window explicitly.
	"""
	return load_frozen_model(
		path,
		train_start=train_start or datetime(1970, 1, 1),
		train_end=train_end,
		model_version=model_version,
		long_threshold=long_threshold,
		short_threshold=short_threshold,
	)
