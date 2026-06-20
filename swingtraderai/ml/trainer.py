import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple, TypeAlias, Union
from uuid import UUID

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from xgboost import XGBClassifier

from swingtraderai.db.session import get_db
from swingtraderai.indicators.matrix import add_all_indicators
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

ArrayLike: TypeAlias = np.ndarray[Any, Any]


class PurgedTimeSeriesSplit(TimeSeriesSplit):
	def __init__(self, n_splits: int = 6, purge_size: int = 12) -> None:
		super().__init__(n_splits=n_splits)
		self.purge_size = purge_size

	def split(
		self,
		X: Union[np.ndarray[Any, Any], List[Any], Any],
		y: Any = None,
		groups: Any = None,
	) -> Generator[Tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]], None, None]:
		for train_idx, test_idx in super().split(X, y, groups):
			if self.purge_size < len(train_idx):
				train_idx = train_idx[: -self.purge_size]
			yield train_idx, test_idx


def calculate_trading_metrics(
	y_true: Union[NDArray[np.float64], List[float]],
	y_pred_proba: Union[NDArray[np.float64], List[float]],
	threshold: float = 0.5,
) -> Dict[str, float]:
	y_true = np.asarray(y_true)
	y_pred_proba = np.asarray(y_pred_proba)
	y_pred = (y_pred_proba > threshold).astype(int)

	total_trades = int(np.sum(y_pred))
	if total_trades == 0:
		return {"win_rate": 0.0, "total_trades": 0.0, "profit_factor": 0.0}

	winning_trades = int(np.sum((y_pred == 1) & (y_true == 1)))
	win_rate = winning_trades / total_trades

	avg_win_conf = (
		float(np.mean(y_pred_proba[y_true == 1])) if np.any(y_true == 1) else 0.0
	)
	avg_loss_conf = (
		float(np.mean(y_pred_proba[y_true == 0])) if np.any(y_true == 0) else 1.0
	)

	profit_factor = (win_rate * avg_win_conf) / ((1 - win_rate) * avg_loss_conf + 1e-6)

	return {
		"win_rate": float(win_rate),
		"total_trades": float(total_trades),
		"profit_factor": float(profit_factor),
	}


def get_atr_column(df: pd.DataFrame) -> str:
	"""Безопасно находим колонку ATR"""
	for col in ["atr14", "atr_14", "atr", "ATR14", "ATR_14"]:
		if col in df.columns:
			return col
	# Если нет — создаём простую версию
	if "high" in df.columns and "low" in df.columns and "close" in df.columns:
		df["atr_calc"] = df["high"] - df["low"]
		return "atr_calc"
	raise KeyError("ATR column not found and could not be calculated")


def detect_strong_levels(
	df: pd.DataFrame, min_tests: int = 3, window: int = 120
) -> pd.DataFrame:
	"""Обнаружение сильных уровней"""
	df = df.copy()

	df["swing_high"] = df["high"][
		(df["high"] == df["high"].rolling(window, center=True).max())
	]
	df["swing_low"] = df["low"][
		(df["low"] == df["low"].rolling(window, center=True).min())
	]

	levels: List[Dict[str, Any]] = []
	for col, level_type in [("swing_high", "resistance"), ("swing_low", "support")]:
		valid = df[col].dropna()
		for price in valid:
			tests = ((df["high"] >= price * 0.995) & (df["low"] <= price * 1.005)).sum()
			if tests >= min_tests:
				levels.append(
					{"price": float(price), "type": level_type, "tests": int(tests)}
				)

	# Добавляем признаки уровней
	df["nearest_level"] = np.nan
	df["level_type"] = ""
	df["level_strength"] = 0.0
	df["dist_to_level"] = 0.0

	for i in range(len(df)):
		close = df["close"].iloc[i]
		candidates = [
			level for level in levels if abs(level["price"] - close) / close < 0.08
		]  # до 8%
		if candidates:
			best = max(
				candidates,
				key=lambda x: int(x["tests"]),  # Явное приведение к int
			)
			df.loc[df.index[i], "nearest_level"] = best["price"]
			df.loc[df.index[i], "level_type"] = best["type"]
			df.loc[df.index[i], "level_strength"] = best["tests"]
			df.loc[df.index[i], "dist_to_level"] = (close - best["price"]) / best[
				"price"
			]

	return df


def detect_false_breakout(df: pd.DataFrame, atr_mult: float = 1.3) -> pd.DataFrame:
	"""Определение ложных пробоев — исправленная версия"""
	df = df.copy()
	atr_col = get_atr_column(df)
	atr = df[atr_col]

	df["false_breakout"] = 0
	df["fb_type"] = ""
	df["fb_depth"] = 0.0
	df["fb_return_bars"] = 0

	for i in range(5, len(df) - 10):
		if pd.isna(df["nearest_level"].iloc[i]):
			continue

		level = df["nearest_level"].iloc[i]
		level_type = df["level_type"].iloc[i]
		current_atr = atr.iloc[i]

		# Bear Trap (ложный пробой поддержки вниз → Long)
		if level_type == "support":
			if df["low"].iloc[i] < level * 0.995 and df["close"].iloc[i] > level:
				depth = (level - df["low"].iloc[i]) / current_atr
				if depth > 0.4:  # чуть строже
					df.loc[df.index[i], "false_breakout"] = 1
					df.loc[df.index[i], "fb_type"] = "bear_trap"
					df.loc[df.index[i], "fb_depth"] = float(depth)
					for j in range(1, 8):
						if df["close"].iloc[i + j] > level:
							df.loc[df.index[i], "fb_return_bars"] = j
							break

		# Bull Trap (ложный пробой сопротивления вверх → Short)
		elif level_type == "resistance":
			if df["high"].iloc[i] > level * 1.005 and df["close"].iloc[i] < level:
				depth = (df["high"].iloc[i] - level) / current_atr
				if depth > 0.4:
					df.loc[df.index[i], "false_breakout"] = 1
					df.loc[df.index[i], "fb_type"] = "bull_trap"
					df.loc[df.index[i], "fb_depth"] = float(depth)
					for j in range(1, 8):
						if df["close"].iloc[i + j] < level:
							df.loc[df.index[i], "fb_return_bars"] = j
							break

	return df


async def train_model(
	ticker_id: UUID,
	timeframe: str = "1h",
	n_splits: int = 6,
	early_stopping_rounds: int = 80,
	verbose: bool = True,
) -> str:
	# ===================== LOAD DATA =====================
	async with asynccontextmanager(get_db)() as session:
		cols = ", ".join(MARKET_DATA_SCHEMA.BASE_COLUMNS)
		query = text(
			f"""
			SELECT {cols}
			FROM market_data
			WHERE ticker_id = :ticker_id AND timeframe = :tf
			ORDER BY {MARKET_DATA_SCHEMA.TIME_COLUMN}
		"""
		)
		result = await session.execute(query, {"ticker_id": ticker_id, "tf": timeframe})
		rows = result.fetchall()

	if not rows:
		raise ValueError("Нет данных")

	df = pd.DataFrame(rows, columns=MARKET_DATA_SCHEMA.BASE_COLUMNS)
	df[MARKET_DATA_SCHEMA.TIME_COLUMN] = pd.to_datetime(
		df[MARKET_DATA_SCHEMA.TIME_COLUMN]
	)

	# ===================== INDICATORS =====================
	df = add_all_indicators(df, timeframe=timeframe)

	# ===================== GERCHIK FEATURES =====================
	df = detect_strong_levels(df, min_tests=3, window=120)
	df = detect_false_breakout(df, atr_mult=1.3)

	# Дополнительные фичи
	df["returns_5"] = df["close"].pct_change(5)
	df["returns_10"] = df["close"].pct_change(10)
	df["volume_ratio"] = df["volume"] / df["volume"].rolling(30).mean()
	df["price_to_level_ratio"] = df["close"] / (
		df.get("nearest_level", df["close"]) + 1e-8
	)
	df["level_strength_rank"] = df["level_strength"].rolling(200).rank(pct=True)

	df = df.dropna().reset_index(drop=True)

	# ===================== TARGET =====================
	horizon = 15
	df["target"] = 0

	for i in range(len(df) - horizon):
		if df["false_breakout"].iloc[i] == 1:
			fb_type = df["fb_type"].iloc[i]
			entry = df["close"].iloc[i]

			future_high = df["high"].iloc[i + 1 : i + horizon + 1].max()
			future_low = df["low"].iloc[i + 1 : i + horizon + 1].min()

			if fb_type == "bear_trap" and future_high > entry * 1.012:
				df.loc[i, "target"] = 1
			elif fb_type == "bull_trap" and future_low < entry * 0.988:
				df.loc[i, "target"] = 1

	# ===================== FEATURES =====================
	feature_columns = [
		"false_breakout",
		"fb_depth",
		"fb_return_bars",
		"level_strength",
		"dist_to_level",
		"price_to_level_ratio",
		"level_strength_rank",
		"volume_ratio",
		"volume_zscore",
		"volume_spike",
		"rsi14",
		"rsi_delta_3",
		"macd_hist",
		"atr_pct",
		"bb_width",
		"returns_5",
		"returns_10",
		"price_above_ema200",
		"ema9_gt_ema21",
		"hour",
		"dayofweek",
		"is_session_open",
	]

	features = [col for col in feature_columns if col in df.columns]

	X = df[features].copy()
	y = df["target"].copy()

	X = X.iloc[:-horizon].reset_index(drop=True)
	y = y.iloc[:-horizon].reset_index(drop=True)

	if len(X) < 800:
		raise ValueError(f"Недостаточно данных: {len(X)} строк")

	# ===================== TRAINING =====================
	tscv = PurgedTimeSeriesSplit(n_splits=n_splits, purge_size=horizon + 10)

	best_model: Optional[XGBClassifier] = None
	best_scaler: Optional[StandardScaler] = None
	best_auc = -1.0
	cv_results: List[Dict[str, float]] = []

	for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
		X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
		y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

		scaler = StandardScaler()
		X_train_scaled = scaler.fit_transform(X_train)
		X_val_scaled = scaler.transform(X_val)

		pos_ratio = float(y_train.mean())
		scale_pos_weight = (
			max((1 - pos_ratio) / pos_ratio, 1.0) if pos_ratio > 0 else 1.0
		)

		model = XGBClassifier(
			n_estimators=1000,
			learning_rate=0.03,
			max_depth=6,
			min_child_weight=5,
			gamma=0.5,
			subsample=0.8,
			colsample_bytree=0.8,
			reg_alpha=0.6,
			reg_lambda=2.0,
			scale_pos_weight=scale_pos_weight,
			eval_metric=["auc", "logloss"],
			tree_method="hist",
			random_state=42,
			max_bin=512,
		)

		model.fit(
			X_train_scaled,
			y_train,
			eval_set=[(X_val_scaled, y_val)],
			early_stopping_rounds=early_stopping_rounds,
			verbose=False,
		)

		probs = model.predict_proba(X_val_scaled)[:, 1]
		auc = float(roc_auc_score(y_val, probs))
		metrics = calculate_trading_metrics(y_val, probs)

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

	# ===================== SAVE =====================
	if best_model is None or best_scaler is None:
		raise RuntimeError("Training failed: no model was trained")

	avg_metrics = pd.DataFrame(cv_results).mean(numeric_only=True).to_dict()

	model_dir = f"models/gerchik_xgboost/{ticker_id}"
	os.makedirs(model_dir, exist_ok=True)

	timestamp = datetime.now().strftime("%Y%m%d_%H%M")
	path = f"{model_dir}/{ticker_id}_{timeframe}_gerchik_{timestamp}.joblib"

	joblib.dump(
		{
			"model": best_model,
			"scaler": best_scaler,
			"features": features,
			"metrics": avg_metrics,
			"ticker_id": str(ticker_id),
			"timeframe": timeframe,
			"strategy": "gerchik_levels_falsebreakout",
		},
		path,
		compress=3,
	)

	if verbose:
		print(
			f"✅ Gerchik Model trained | AUC: {avg_metrics.get('auc', 0):.4f} | "
			f"WR: {avg_metrics.get('win_rate', 0):.1%} | "
			f"PF: {avg_metrics.get('profit_factor', 0):.2f}"
		)

	return path
