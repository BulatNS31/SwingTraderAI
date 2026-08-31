from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

import joblib
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from swingtraderai.ml.setup_dataset import build_setup_dataset
from swingtraderai.ml.trainer import (
	PurgedTimeSeriesSplit,
	calculate_trading_metrics,
)


def train_setup_model(
	df: pd.DataFrame,
	*,
	symbol: str,
	ticker_id: Optional[UUID] = None,
	timeframe: str = "1D",
	horizon: int = 15,
	label_mode: str = "rr",  # "rr" или "atr"
	atr_mult: float = 1.5,
	n_splits: int = 5,
	min_samples: int = 80,
	verbose: bool = True,
) -> str:
	"""
	Обучение фильтра setup'ов. Сохраняет joblib с model, scaler, features.
	"""
	X, y = build_setup_dataset(
		df,
		symbol=symbol,
		timeframe=timeframe,
		horizon=horizon,
		label_mode=label_mode,
		atr_mult=atr_mult,
	)

	if len(X) < min_samples:
		raise ValueError(
			f"Мало размеченных setup'ов: {len(X)} (нужно ≥ {min_samples}). "
			"Увеличьте историю или ослабьте фильтры сканера."
		)

	if verbose:
		print(f"Setup dataset: {len(X)} | positive rate: {y.mean():.1%}")

	features = list(X.columns)
	tscv = PurgedTimeSeriesSplit(
		n_splits=min(n_splits, max(2, len(X) // 30)), purge_size=5
	)

	best_model: Optional[XGBClassifier] = None
	best_scaler: Optional[StandardScaler] = None
	best_auc = -1.0
	cv_results: List[Dict[str, float]] = []

	for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
		X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
		y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

		if y_train.nunique() < 2 or y_val.nunique() < 2:
			continue

		scaler = StandardScaler()
		X_train_s = scaler.fit_transform(X_train)
		X_val_s = scaler.transform(X_val)

		pos = float(y_train.mean())
		spw = max((1 - pos) / pos, 1.0) if pos > 0 else 1.0

		model = XGBClassifier(
			n_estimators=400,
			learning_rate=0.05,
			max_depth=4,
			min_child_weight=5,
			gamma=0.3,
			subsample=0.8,
			colsample_bytree=0.8,
			reg_alpha=0.5,
			reg_lambda=1.5,
			scale_pos_weight=spw,
			eval_metric=["auc", "logloss"],
			tree_method="hist",
			random_state=42,
		)
		model.fit(X_train_s, y_train, eval_set=[(X_val_s, y_val)], verbose=False)

		probs = model.predict_proba(X_val_s)[:, 1]
		auc = float(roc_auc_score(y_val, probs))
		metrics = calculate_trading_metrics(y_val, probs, threshold=0.5)
		cv_results.append(
			{
				"fold": float(fold),
				"auc": auc,
				"win_rate": metrics["win_rate"],
				"trades": metrics["total_trades"],
				"profit_factor": metrics["profit_factor"],
			}
		)
		if auc > best_auc:
			best_auc = auc
			best_model = model
			best_scaler = scaler

	if best_model is None or best_scaler is None:
		# fallback: fit on all data
		scaler = StandardScaler()
		Xs = scaler.fit_transform(X)
		pos = float(y.mean())
		spw = max((1 - pos) / pos, 1.0) if pos > 0 else 1.0
		best_model = XGBClassifier(
			n_estimators=300,
			learning_rate=0.05,
			max_depth=4,
			scale_pos_weight=spw,
			tree_method="hist",
			random_state=42,
		)
		best_model.fit(Xs, y)
		best_scaler = scaler
		best_auc = 0.0

	avg = (
		pd.DataFrame(cv_results).mean(numeric_only=True).to_dict() if cv_results else {}
	)
	tid = str(ticker_id) if ticker_id else symbol
	model_dir = f"models/setup_xgboost/{tid}"
	os.makedirs(model_dir, exist_ok=True)
	ts = datetime.now().strftime("%Y%m%d_%H%M")
	path = f"{model_dir}/{tid}_{timeframe}_setups_{ts}.joblib"

	joblib.dump(
		{
			"model": best_model,
			"scaler": best_scaler,
			"features": features,
			"metrics": avg,
			"symbol": symbol,
			"ticker_id": tid,
			"timeframe": timeframe,
			"horizon": horizon,
			"label_mode": label_mode,
			"strategy": "setup_filter",
		},
		path,
		compress=3,
	)

	if verbose:
		print(
			f"✅ Setup model | n={len(X)} | AUC: {avg.get('auc', best_auc):.4f} | "
			f"WR: {avg.get('win_rate', 0):.1%} | → {path}"
		)
	return path
